from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
import datetime

from backend.database import get_db
from backend.models import (
    Product, InventoryLedger, Warehouse, Order, OrderItem,
    ProductReview, Vendor, DemandForecast, User
)
from backend.schemas import (
    VendorPerformanceOut, DemandForecastOut, InventoryPlanningOut,
    SentimentAnalysisOut, SentimentReviewOut,
    AddStockRequest, AddStockResponse,
    VendorSetupRequest, AddProductRequest
)

from typing import Optional

router = APIRouter(prefix="/api/ai", tags=["AI & Analytics"])

# ── Sentiment Analysis ───────────────────────────────────────────────────────
@router.get("/sentiment-analysis", response_model=list[SentimentAnalysisOut])
def get_sentiment_analysis(vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Product)
    if vendor_id is not None:
        query = query.filter(Product.vendor_id == vendor_id)
    products = query.all()
    results = []
    
    for p in products:
        reviews = db.query(ProductReview).filter(ProductReview.product_id == p.product_id).all()
        if not reviews:
            continue
            
        scored = [r for r in reviews if r.ai_sentiment_score is not None]
        total_scored = len(scored)
        
        if total_scored == 0:
            avg_sent = 0.0
            pos = 0.0
            neg = 0.0
        else:
            avg_sent = sum(float(r.ai_sentiment_score) for r in scored) / total_scored
            positive = len([r for r in scored if float(r.ai_sentiment_score) >= 0.6])
            negative = len([r for r in scored if float(r.ai_sentiment_score) <= 0.4])
            pos = positive / total_scored
            neg = negative / total_scored
            
        recent = [
            SentimentReviewOut(
                star_rating=r.star_rating,
                review_body=r.review_body,
                ai_sentiment_score=float(r.ai_sentiment_score) if r.ai_sentiment_score is not None else None
            )
            for r in sorted(reviews, key=lambda x: x.created_at, reverse=True)[:5]
        ]
        
        results.append(SentimentAnalysisOut(
            product_id=p.product_id,
            name=p.name,
            average_sentiment=avg_sent,
            total_reviews=len(reviews),
            positive_ratio=pos,
            negative_ratio=neg,
            recent_reviews=recent
        ))
        
    return results


# ── Vendor Performance ───────────────────────────────────────────────────────
@router.get("/vendor-performance", response_model=list[VendorPerformanceOut])
def get_vendor_performance(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).all()
    results = []
    
    def get_letter_grade(score):
        if score is None: return "N/A"
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"
        
    for v in vendors:
        results.append(VendorPerformanceOut(
            vendor_id=v.vendor_id,
            vendor_name=v.vendor_name,
            performance_score=v.performance_score,
            letter_grade=get_letter_grade(float(v.performance_score) if v.performance_score else None),
            warehouse_count=v.warehouse_count
        ))
    return results

@router.put("/vendor/setup")
def setup_vendor(payload: VendorSetupRequest, vendor_id: int, db: Session = Depends(get_db)):
    """One-time setup for vendor to store their total number of warehouses."""
    vendor = db.query(Vendor).filter(Vendor.vendor_id == str(vendor_id)).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    
    vendor.warehouse_count = payload.warehouse_count
    db.commit()
    return {"message": "Vendor setup complete.", "warehouse_count": vendor.warehouse_count}


# ── Demand Forecasting ───────────────────────────────────────────────────────
@router.get("/demand-forecasting", response_model=list[DemandForecastOut])
def get_demand_forecasting(vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Product)
    if vendor_id is not None:
        query = query.filter(Product.vendor_id == vendor_id)
    products = query.all()
    results = []
    
    for p in products:
        ledger = db.query(func.sum(InventoryLedger.qty_available)).filter(
            InventoryLedger.product_id == p.product_id
        ).scalar()
        current_stock = int(ledger) if ledger else 0
        
        forecast = db.query(func.avg(DemandForecast.predicted_demand)).filter(
            DemandForecast.product_id == p.product_id
        ).scalar()
        
        velocity_daily = float(forecast) if forecast else 1.5
        days_remaining = int(current_stock / velocity_daily) if velocity_daily > 0 else 999
        
        if days_remaining <= 14:
            rec = "RESTOCK NOW"
        elif days_remaining <= 30:
            rec = "RESTOCK SOON"
        else:
            rec = "OPTIMAL"
            
        results.append(DemandForecastOut(
            product_id=p.product_id,
            sku=p.sku,
            name=p.name,
            current_stock=current_stock,
            velocity_daily=velocity_daily,
            days_remaining=days_remaining,
            recommendation=rec
        ))
    return results


# ── Inventory Planning ───────────────────────────────────────────────────────
@router.get("/inventory-planning", response_model=list[InventoryPlanningOut])
def get_inventory_planning(vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(InventoryLedger)
    if vendor_id is not None:
        query = query.join(Product).filter(Product.vendor_id == vendor_id)
    ledgers = query.all()
    results = []
    
    for ledg in ledgers:
        product = ledg.product
        warehouse = ledg.warehouse
        
        forecast = db.query(func.avg(DemandForecast.predicted_demand)).filter(
            DemandForecast.product_id == product.product_id
        ).scalar()
        
        velocity_daily = float(forecast) if forecast else 1.5
        reorder_point = int(velocity_daily * 14) # 14 day lead time buffer
        
        if ledg.qty_available <= reorder_point:
            status = "CRITICAL"
        elif ledg.qty_available <= reorder_point * 2:
            status = "WARNING"
        else:
            status = "HEALTHY"
            
        results.append(InventoryPlanningOut(
            product_id=product.product_id,
            sku=product.sku,
            name=product.name,
            warehouse=warehouse.location_name if warehouse else "Main",
            qty_available=ledg.qty_available,
            qty_reserved=ledg.qty_reserved,
            reorder_point=reorder_point,
            status=status
        ))
    return results


# ── Add Stock (Vendor Restock) ───────────────────────────────────────────────
@router.post("/add-stock", response_model=AddStockResponse)
def add_stock(payload: AddStockRequest, vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Atomically increase stock for a vendor's product using FOR UPDATE locking.
    vendor_id query param identifies the calling vendor (matched against Product.vendor_id).
    """
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be a positive integer.")

    # Verify the product exists and belongs to this vendor
    product = db.query(Product).filter(Product.product_id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if vendor_id is not None and product.vendor_id != vendor_id:
        raise HTTPException(status_code=403, detail="You can only restock your own products.")

    # Atomically lock and update the inventory row
    ledger = (
        db.query(InventoryLedger)
        .filter(
            InventoryLedger.product_id == payload.product_id,
            InventoryLedger.warehouse_id == payload.warehouse_id,
        )
        .with_for_update()  # Pessimistic row-level lock
        .first()
    )

    if not ledger:
        # Create a new ledger entry if one doesn't exist for this product/warehouse combo
        ledger = InventoryLedger(
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            qty_available=payload.quantity,
            qty_reserved=0,
        )
        db.add(ledger)
    else:
        ledger.qty_available += payload.quantity

    db.commit()
    db.refresh(ledger)

    return AddStockResponse(
        product_id=payload.product_id,
        warehouse_id=payload.warehouse_id,
        new_qty_available=ledger.qty_available,
        message=f"Added {payload.quantity} units. New stock: {ledger.qty_available}"
    )

# ── Add Product (Catalog) ─────────────────────────────────────────
@router.post("/products")
def add_product(payload: AddProductRequest, vendor_id: int, db: Session = Depends(get_db)):
    """
    Creates a new product and initializes its stock.
    Operations are wrapped in a single atomic transaction.
    """
    # 1. Verify Vendor exists (using User table since products.vendor_id refers to users.user_id)
    user = db.query(User).filter(User.user_id == vendor_id).first()
    if not user or not any(r.role_name == "Vendor" for r in user.roles):
        raise HTTPException(status_code=404, detail="Vendor user not found.")

    try:
        # 2. Create Product
        new_product = Product(
            vendor_id=vendor_id,
            sku=payload.sku,
            name=payload.name,
            description=payload.description,
            price=payload.price
        )
        db.add(new_product)
        db.flush()  # To get the product_id
        
        # 2.5 Verify Warehouse exists
        from backend.models import Warehouse
        warehouse = db.query(Warehouse).filter(Warehouse.warehouse_id == payload.warehouse_id).first()
        if not warehouse:
            raise HTTPException(status_code=400, detail=f"Warehouse with ID {payload.warehouse_id} does not exist. Please provide a valid warehouse_id.")

        # 3. Initialize Stock
        ledger = InventoryLedger(
            product_id=new_product.product_id,
            warehouse_id=payload.warehouse_id,
            qty_available=payload.initial_qty,
            qty_reserved=0
        )
        db.add(ledger)

        db.commit()
        return {"message": "Product created successfully along with initial stock.", "product_id": new_product.product_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
