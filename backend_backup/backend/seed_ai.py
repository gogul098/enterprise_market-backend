import sys
import os
import datetime
from decimal import Decimal

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Base, engine
from backend.models import (
    Role, User, Product, Warehouse, InventoryLedger,
    Vendor, DemandForecast, ProductReview, Order, OrderItem
)
from backend.seed import seed as run_base_seed

def seed_ai():
    print("🔄 Running base seed to ensure products, warehouse, and user exist...")
    run_base_seed()

    db = SessionLocal()
    try:
        print("🌱 Seeding AI tables...")

        # 1. Seed Vendor performance entries
        # Check if they exist first
        vendor_data = [
            {"vendor_id": "1", "vendor_name": "Central Fulfillment Hub — Bangalore", "performance_score": Decimal("94.20")},
            {"vendor_id": "2", "vendor_name": "AsiaTech Direct", "performance_score": Decimal("86.50")},
            {"vendor_id": "3", "vendor_name": "Logistics Pro India", "performance_score": Decimal("55.10")},
        ]
        
        for v in vendor_data:
            existing = db.query(Vendor).filter(Vendor.vendor_id == v["vendor_id"]).first()
            if not existing:
                db.add(Vendor(
                    vendor_id=v["vendor_id"],
                    vendor_name=v["vendor_name"],
                    performance_score=v["performance_score"]
                ))
        print("✅ Seeded Vendor Performance data")

        # Get seeded objects
        products = db.query(Product).all()
        warehouse = db.query(Warehouse).first()
        wh_id = warehouse.warehouse_id if warehouse else 1
        
        if not products:
            print("❌ Error: No products found. Seed failed.")
            return

        # 2. Seed Demand Forecast entries
        # Create forecasts for the next 7 days for each product
        today = datetime.datetime.now()
        for p in products:
            existing_fc = db.query(DemandForecast).filter(DemandForecast.product_id == p.product_id).first()
            if not existing_fc:
                # Let's seed 1 forecast row per product
                predicted = Decimal("15.5") if p.product_id % 2 == 0 else Decimal("4.2")
                db.add(DemandForecast(
                    product_id=p.product_id,
                    warehouse_id=wh_id,
                    target_date=today + datetime.timedelta(days=1),
                    predicted_demand=predicted,
                    confidence_lower_bound=predicted - Decimal("1.2"),
                    confidence_upper_bound=predicted + Decimal("1.5")
                ))
        print("✅ Seeded Demand Forecasts")



        # 4. Seed Product Reviews with PyTorch sentiment scores
        reviews_pool = [
            {"headline": "Amazing product!", "body": "Absolutely love this item, works exactly as described. Battery life is fantastic.", "score": 0.98, "rating": 5},
            {"headline": "Decent purchase", "body": "It is okay. Build quality is solid but features are average.", "score": 0.52, "rating": 3},
            {"headline": "Terrible quality", "body": "Stopped working after two days. Extremely disappointing customer service.", "score": 0.05, "rating": 1},
            {"headline": "Satisfied", "body": "Works fine. Easy to set up and fast delivery.", "score": 0.81, "rating": 4},
            {"headline": "Not recommended", "body": "Too expensive for what it is. Scratched on arrival.", "score": 0.22, "rating": 2},
        ]
        
        # Create a buyer user to be the reviewer
        buyer_email = "buyer@marketplace.com"
        buyer = db.query(User).filter(User.email == buyer_email).first()
        if not buyer:
            from backend.auth import hash_password
            buyer = User(
                email=buyer_email,
                password_hash=hash_password("buyer123")
            )
            db.add(buyer)
            db.flush()
            buyer_role = db.query(Role).filter(Role.role_name == "Buyer").first()
            if buyer_role:
                buyer.roles.append(buyer_role)
                
        for i, p in enumerate(products):
            existing_rev = db.query(ProductReview).filter(ProductReview.product_id == p.product_id).first()
            if not existing_rev:
                # Add 2 reviews per product
                rev1 = reviews_pool[i % len(reviews_pool)]
                rev2 = reviews_pool[(i + 1) % len(reviews_pool)]
                
                db.add(ProductReview(
                    product_id=p.product_id,
                    buyer_id=buyer.user_id,
                    star_rating=rev1["rating"],
                    review_headline=rev1["headline"],
                    review_body=rev1["body"],
                    ai_sentiment_score=Decimal(str(rev1["score"])),
                    verified_purchase=True
                ))
                db.add(ProductReview(
                    product_id=p.product_id,
                    buyer_id=buyer.user_id,
                    star_rating=rev2["rating"],
                    review_headline=rev2["headline"],
                    review_body=rev2["body"],
                    ai_sentiment_score=Decimal(str(rev2["score"])),
                    verified_purchase=True
                ))
        print("✅ Seeded Product Reviews & PyTorch Sentiment scores")

        # 5. Seed sample orders so the smart route map has coordinates/markers to draw
        existing_orders = db.query(Order).first()
        if not existing_orders:
            # We seed a few pending orders
            for j in range(4):
                order = Order(
                    buyer_id=buyer.user_id,
                    total_amount=Decimal("15000.00"),
                    global_status="pending"
                )
                db.add(order)
                db.flush()
                
                db.add(OrderItem(
                    order_id=order.order_id,
                    product_id=products[j % len(products)].product_id,
                    warehouse_id=wh_id,
                    quantity=1,
                    unit_price=Decimal("15000.00")
                ))
            print("✅ Seeded Orders for Route Maps")

        db.commit()
        print("\n🎉 AI Seed complete! Your AI Control Center has data ready to show.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_ai()
