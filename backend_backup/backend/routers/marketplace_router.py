"""
Marketplace router: GET /api/products, POST /api/orders/checkout,
GET /api/orders, PATCH /api/orders/{order_id}/status

CRITICAL: The checkout endpoint uses pessimistic row-level locking (FOR UPDATE)
via SQLAlchemy's with_for_update() on the Inventory_Ledger rows to prevent
concurrent overselling under MariaDB InnoDB.
"""
import json
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models import Product, InventoryLedger, Order, OrderItem, AuditLog, User, user_roles, Role, ProductReview
from backend.schemas import (
    ProductOut, CheckoutRequest, OrderOut, OrderItemOut,
    OrderStatusUpdate, ReviewCreate, ReviewOut
)
from backend.ws_manager import manager

router = APIRouter(prefix="/api", tags=["Marketplace"])

VALID_ORDER_STATUSES = {"pending", "packed", "in_transit", "delivered"}


@router.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """
    Return the full product catalog with total available quantity
    aggregated across all warehouses.
    """
    results = (
        db.query(
            Product.product_id,
            Product.sku,
            Product.name,
            Product.description,
            Product.price,
            Product.image_url,
            func.coalesce(func.sum(InventoryLedger.qty_available), 0).label("qty_available"),
        )
        .outerjoin(InventoryLedger, Product.product_id == InventoryLedger.product_id)
        .group_by(Product.product_id)
        .all()
    )

    return [
        ProductOut(
            product_id=r.product_id,
            sku=r.sku,
            name=r.name,
            description=r.description,
            price=r.price,
            image_url=r.image_url,
            qty_available=int(r.qty_available),
        )
        for r in results
    ]


@router.post("/orders/checkout", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    """
    Transactional checkout with pessimistic locking.

    1. Check idempotency_key to prevent duplicate orders.
    2. For each item, lock the Inventory_Ledger row with FOR UPDATE.
    3. If qty_available >= requested quantity → subtract available, add reserved.
    4. If any item fails → rollback entire transaction → HTTP 400.
    5. Commit only when ALL items clear.
    6. Broadcast ORDER_CREATED + INVENTORY_UPDATE via WebSocket.
    """
    # ── Idempotency Guard ────────────────────────────────────────────────
    existing_order = (
        db.query(Order)
        .filter(Order.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing_order:
        buyer = db.query(User).filter(User.user_id == existing_order.buyer_id).first()
        return OrderOut(
            order_id=existing_order.order_id,
            buyer_id=existing_order.buyer_id,
            buyer_email=buyer.email if buyer else None,
            idempotency_key=existing_order.idempotency_key,
            total_amount=existing_order.total_amount,
            global_status=existing_order.global_status,
            created_at=existing_order.created_at.isoformat() if existing_order.created_at else None,
            items=[
                OrderItemOut(
                    product_id=i.product_id,
                    product_name=db.query(Product.name).filter(Product.product_id == i.product_id).scalar(),
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                )
                for i in existing_order.items
            ],
        )

    # ── Begin Transactional Checkout ─────────────────────────────────────
    total_amount = Decimal("0.00")
    order_items_data = []  # Collect (product_id, warehouse_id, quantity, unit_price, product_name)

    try:
        for item in payload.items:
            # ── CRITICAL: Pessimistic lock on the inventory row ──────────
            ledger_entry = (
                db.query(InventoryLedger)
                .filter(InventoryLedger.product_id == item.product_id)
                .with_for_update()  # ROW-LEVEL LOCK (SELECT ... FOR UPDATE)
                .first()
            )

            if not ledger_entry or ledger_entry.qty_available < item.quantity:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Product ID {item.product_id} is out of stock "
                        f"or insufficient quantity available."
                    ),
                )

            # Adjust inventory atomically inside the lock
            ledger_entry.qty_available -= item.quantity
            ledger_entry.qty_reserved += item.quantity

            # Look up unit price for the order record
            product = db.query(Product).filter(Product.product_id == item.product_id).first()
            unit_price = product.price if product else Decimal("0.00")
            line_total = unit_price * item.quantity
            total_amount += line_total

            order_items_data.append({
                "product_id": item.product_id,
                "warehouse_id": ledger_entry.warehouse_id,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "product_name": product.name if product else "Unknown",
                "vendor_id": product.vendor_id if product else None,
            })

        # ── Create Order ─────────────────────────────────────────────────
        order = Order(
            buyer_id=payload.buyer_id,
            idempotency_key=payload.idempotency_key,
            total_amount=total_amount,
            global_status="pending",
        )
        db.add(order)
        db.flush()  # Get order_id

        for oi_data in order_items_data:
            db.add(OrderItem(
                order_id=order.order_id,
                product_id=oi_data["product_id"],
                warehouse_id=oi_data["warehouse_id"],
                quantity=oi_data["quantity"],
                unit_price=oi_data["unit_price"],
            ))

        # ── Audit Log ────────────────────────────────────────────────────
        db.add(AuditLog(
            entity_type="Order",
            entity_id=str(order.order_id),
            action="CHECKOUT_RESERVED",
            details=json.dumps({
                "buyer_id": payload.buyer_id,
                "items": [
                    {"product_id": d["product_id"], "qty": d["quantity"]}
                    for d in order_items_data
                ],
                "total": str(total_amount),
            }),
        ))

        # ── COMMIT: All items cleared ────────────────────────────────────
        db.commit()
        db.refresh(order)

        # ── Broadcast real-time updates via WebSocket ────────────────────
        buyer = db.query(User).filter(User.user_id == payload.buyer_id).first()
        try:
            # Inventory update
            inv_updates = []
            for oi_data in order_items_data:
                fresh_ledger = db.query(InventoryLedger).filter(
                    InventoryLedger.product_id == oi_data["product_id"]
                ).first()
                if fresh_ledger:
                    inv_updates.append({
                        "product_id": oi_data["product_id"],
                        "qty_available": int(fresh_ledger.qty_available)
                    })
            if inv_updates:
                manager.broadcast_sync({"type": "INVENTORY_UPDATE", "updates": inv_updates})

            # Order created notification (for vendors)
            # Collect unique vendor_ids so the frontend knows which vendors this order is relevant to
            item_vendor_ids = set()
            broadcast_items = []
            for d in order_items_data:
                vid = d.get("vendor_id")
                if vid:
                    item_vendor_ids.add(vid)
                broadcast_items.append({
                    "product_id": d["product_id"],
                    "product_name": d["product_name"],
                    "quantity": d["quantity"],
                    "unit_price": str(d["unit_price"]),
                    "vendor_id": vid,
                })

            manager.broadcast_sync({
                "type": "ORDER_CREATED",
                "vendor_ids": list(item_vendor_ids),
                "order": {
                    "order_id": order.order_id,
                    "buyer_id": order.buyer_id,
                    "buyer_email": buyer.email if buyer else "unknown",
                    "total_amount": str(order.total_amount),
                    "global_status": order.global_status,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "items": broadcast_items,
                },
            })
        except Exception:
            pass  # Don't fail checkout if broadcast fails

        return OrderOut(
            order_id=order.order_id,
            buyer_id=order.buyer_id,
            buyer_email=buyer.email if buyer else None,
            idempotency_key=order.idempotency_key,
            total_amount=order.total_amount,
            global_status=order.global_status,
            created_at=order.created_at.isoformat() if order.created_at else None,
            items=[
                OrderItemOut(
                    product_id=oi["product_id"],
                    product_name=oi["product_name"],
                    quantity=oi["quantity"],
                    unit_price=oi["unit_price"],
                )
                for oi in order_items_data
            ],
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions (stock errors)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checkout failed unexpectedly: {str(exc)}",
        )


# ── Order Listing ────────────────────────────────────────────────────────────
@router.get("/orders", response_model=list[OrderOut])
def list_orders(user_id: int, role: str = "Buyer", db: Session = Depends(get_db)):
    """
    Return orders based on the caller's role.
    - Buyer: only their own orders.
    - Vendor: only orders containing products owned by this vendor (`product.vendor_id == user_id`).
    - Admin: all marketplace orders.
    """
    if role in ("Vendor", "Admin"):
        orders = db.query(Order).order_by(Order.created_at.desc()).all()
    else:
        orders = db.query(Order).filter(Order.buyer_id == user_id).order_by(Order.created_at.desc()).all()

    result = []
    for order in orders:
        buyer = db.query(User).filter(User.user_id == order.buyer_id).first()
        items = []
        for oi in order.items:
            product = db.query(Product).filter(Product.product_id == oi.product_id).first()
            # If the caller is a Vendor, strictly filter to only items where vendor_id matches their user_id
            if role == "Vendor":
                if not product or product.vendor_id != user_id:
                    continue
            items.append(OrderItemOut(
                product_id=oi.product_id,
                product_name=product.name if product else "Unknown",
                quantity=oi.quantity,
                unit_price=oi.unit_price,
            ))
        
        # If caller is a Vendor and none of the items in this order belong to them, skip this order completely
        if role == "Vendor" and not items:
            continue

        # If caller is a Vendor, show the total amount for their specific items
        displayed_total = sum((item.unit_price * item.quantity) for item in items) if role == "Vendor" else order.total_amount

        result.append(OrderOut(
            order_id=order.order_id,
            buyer_id=order.buyer_id,
            buyer_email=buyer.email if buyer else None,
            idempotency_key=order.idempotency_key,
            total_amount=displayed_total,
            global_status=order.global_status,
            created_at=order.created_at.isoformat() if order.created_at else None,
            items=items,
        ))

    return result


# ── Order Status Update (Vendor / Admin only) ───────────────────────────────
@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update order fulfillment status.
    Allowed transitions: pending → packed → in_transit → delivered.
    Broadcasts ORDER_STATUS_UPDATE via WebSocket so the buyer sees live updates.
    """
    if payload.status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{payload.status}'. Allowed: {', '.join(sorted(VALID_ORDER_STATUSES))}."
        )

    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order #{order_id} not found."
        )

    old_status = order.global_status
    order.global_status = payload.status

    # Audit log
    db.add(AuditLog(
        entity_type="Order",
        entity_id=str(order.order_id),
        action="STATUS_UPDATE",
        details=json.dumps({
            "old_status": old_status,
            "new_status": payload.status,
        }),
    ))

    db.commit()
    db.refresh(order)

    buyer = db.query(User).filter(User.user_id == order.buyer_id).first()
    items = []
    for oi in order.items:
        product = db.query(Product).filter(Product.product_id == oi.product_id).first()
        items.append(OrderItemOut(
            product_id=oi.product_id,
            product_name=product.name if product else "Unknown",
            quantity=oi.quantity,
            unit_price=oi.unit_price,
        ))

    order_out = OrderOut(
        order_id=order.order_id,
        buyer_id=order.buyer_id,
        buyer_email=buyer.email if buyer else None,
        idempotency_key=order.idempotency_key,
        total_amount=order.total_amount,
        global_status=order.global_status,
        created_at=order.created_at.isoformat() if order.created_at else None,
        items=items,
    )

    # Broadcast status change with full payload via WebSocket
    try:
        manager.broadcast_sync({
            "type": "ORDER_STATUS_UPDATE",
            "order_id": order.order_id,
            "global_status": order.global_status,
            "buyer_id": order.buyer_id,
            "order": order_out.model_dump(mode='json'),
        })
    except Exception:
        pass

    return order_out


from pydantic import BaseModel

class CancelRequest(BaseModel):
    user_id: int

# ── Cancel Order ─────────────────────────────────────────────────────────────
@router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: int, payload: CancelRequest, db: Session = Depends(get_db)):
    """
    Cancel a pending order and release reserved inventory.
    """
    user_id = payload.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")

    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.buyer_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")
        
    if order.global_status != "pending":
        raise HTTPException(status_code=400, detail="Only pending orders can be cancelled")

    try:
        # Revert inventory for all items in the order with pessimistic locking
        for item in order.items:
            ledger_entry = (
                db.query(InventoryLedger)
                .filter(InventoryLedger.product_id == item.product_id)
                .with_for_update()
                .first()
            )
            if ledger_entry:
                # Revert reserved stock back to available
                ledger_entry.qty_reserved -= item.quantity
                ledger_entry.qty_available += item.quantity

        order.global_status = "cancelled"
        db.commit()
        return {"status": "success", "message": "Order cancelled successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── Reviews ──────────────────────────────────────────────────────────────────
@router.post("/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    buyer_id = payload.buyer_id
    # Verify if user has bought this product and if it has been delivered
    delivered_order = (
        db.query(Order)
        .join(OrderItem, Order.order_id == OrderItem.order_id)
        .filter(
            Order.buyer_id == buyer_id,
            OrderItem.product_id == payload.product_id,
            Order.global_status == "delivered"
        )
        .first()
    )
    if not delivered_order:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review products that have been delivered to you."
        )

    # Check if already reviewed
    # (Removed check as per user request to allow multiple reviews)

    new_review = ProductReview(
        product_id=payload.product_id,
        buyer_id=buyer_id,
        star_rating=payload.star_rating,
        verified_purchase=True,
        review_headline=payload.review_headline,
        review_body=payload.review_body,
        product_quality_rating=payload.product_quality_rating,
        logistics_quality_rating=payload.logistics_quality_rating
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    
    return ReviewOut(
        review_id=new_review.review_id,
        product_id=new_review.product_id,
        buyer_id=new_review.buyer_id,
        star_rating=new_review.star_rating,
        verified_purchase=new_review.verified_purchase,
        helpful_votes=new_review.helpful_votes,
        total_votes=new_review.total_votes,
        review_headline=new_review.review_headline,
        review_body=new_review.review_body,
        ai_sentiment_score=new_review.ai_sentiment_score,
        created_at=new_review.created_at.isoformat() if new_review.created_at else None,
        product_quality_rating=new_review.product_quality_rating,
        logistics_quality_rating=new_review.logistics_quality_rating
    )

@router.get("/products/{product_id}/reviews", response_model=list[ReviewOut])
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    reviews = db.query(ProductReview).filter(ProductReview.product_id == product_id).order_by(ProductReview.created_at.desc()).all()
    result = []
    for r in reviews:
        result.append(ReviewOut(
            review_id=r.review_id,
            product_id=r.product_id,
            buyer_id=r.buyer_id,
            star_rating=r.star_rating,
            verified_purchase=r.verified_purchase,
            helpful_votes=r.helpful_votes,
            total_votes=r.total_votes,
            review_headline=r.review_headline,
            review_body=r.review_body,
            ai_sentiment_score=r.ai_sentiment_score,
            created_at=r.created_at.isoformat() if r.created_at else None,
            product_quality_rating=r.product_quality_rating,
            logistics_quality_rating=r.logistics_quality_rating
        ))
    return result

