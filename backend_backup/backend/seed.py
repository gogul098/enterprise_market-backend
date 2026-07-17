"""
Seed script: Creates roles, a vendor user, sample products, a warehouse,
and inventory entries so the UI has data to display immediately.

Usage:
    cd /home/vedanth/Desktop/geeksforgeekshackathon
    ./venv/bin/python -m backend.seed
"""
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, SessionLocal, Base
from backend.models import Role, User, Product, Warehouse, InventoryLedger, Shipment, Order
from backend.auth import hash_password


def seed():
    """Drop and recreate all tables, then insert seed data."""
    print("🔄 Creating / resetting database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── 1. Seed Roles ────────────────────────────────────────────────
        role_names = ["Buyer", "Vendor", "Admin", "Logistics"]
        for rn in role_names:
            if not db.query(Role).filter(Role.role_name == rn).first():
                db.add(Role(role_name=rn))
        db.flush()
        print("✅ Roles seeded: Buyer, Vendor, Admin")

        # ── 2. Seed Vendor User ──────────────────────────────────────────
        vendor_email = "vendor@marketplace.com"
        vendor = db.query(User).filter(User.email == vendor_email).first()
        if not vendor:
            vendor = User(
                email=vendor_email,
                password_hash=hash_password("vendor123"),
            )
            db.add(vendor)
            db.flush()
            vendor_role = db.query(Role).filter(Role.role_name == "Vendor").first()
            if vendor_role:
                vendor.roles.append(vendor_role)
        print(f"✅ Vendor user: {vendor_email} (ID: {vendor.user_id})")

        # ── 3. Seed Logistics User ──────────────────────────────────────────
        logistics_email = "logistics@marketplace.com"
        logistics = db.query(User).filter(User.email == logistics_email).first()
        if not logistics:
            logistics = User(
                email=logistics_email,
                password_hash=hash_password("logistics123"),
            )
            db.add(logistics)
            db.flush()
            logistics_role = db.query(Role).filter(Role.role_name == "Logistics").first()
            if logistics_role:
                logistics.roles.append(logistics_role)
        print(f"✅ Logistics user: {logistics_email} (ID: {logistics.user_id})")

        # ── 4. Seed Warehouse ────────────────────────────────────────────
        wh = db.query(Warehouse).first()
        if not wh:
            wh = Warehouse(
                location_name="Chennai Dispatch Hub",
                capacity=5000,
                address="Amrita Vishwa Vidyapeetham, Chennai",
                latitude=13.0827,
                longitude=80.2707
            )
            db.add(wh)
            db.flush()
        else:
            wh.location_name = "Chennai Dispatch Hub"
            wh.address = "Amrita Vishwa Vidyapeetham, Chennai"
            wh.latitude = 13.0827
            wh.longitude = 80.2707
            db.flush()
        print(f"✅ Warehouse: {wh.location_name} (ID: {wh.warehouse_id})")

        # ── 5. Seed Products ─────────────────────────────────────────────
        products_data = [
            {
                "sku": "LAPTOP-PRO-001",
                "name": "ProBook Ultralight 15",
                "description": "15.6\" Full HD IPS display, Intel i7, 16GB RAM, 512GB SSD. Ultra-slim enterprise laptop for professionals.",
                "price": 89999.00,
                "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=400",
                "qty": 25,
            },
            {
                "sku": "HEADPHONES-NC-002",
                "name": "SilentWave ANC Headphones",
                "description": "Premium over-ear active noise cancelling headphones with 40-hour battery, Bluetooth 5.3, and studio-grade sound.",
                "price": 12499.00,
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400",
                "qty": 50,
            },
            {
                "sku": "MONITOR-4K-003",
                "name": "CrystalView 4K Monitor 27\"",
                "description": "27\" 4K UHD IPS monitor with 99% sRGB, USB-C PD 65W, height-adjustable ergonomic stand. Perfect for creative workflows.",
                "price": 34999.00,
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400",
                "qty": 15,
            },
            {
                "sku": "KEYBOARD-MECH-004",
                "name": "TypeForce Mechanical Keyboard",
                "description": "Hot-swappable mechanical keyboard with RGB backlighting, Cherry MX Brown switches, full aluminum frame.",
                "price": 7999.00,
                "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400",
                "qty": 80,
            },
            {
                "sku": "MOUSE-ERG-005",
                "name": "GlidePro Ergonomic Mouse",
                "description": "Vertical ergonomic wireless mouse with 4000 DPI sensor, silent clicks, and rechargeable battery lasting 3 months.",
                "price": 2999.00,
                "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400",
                "qty": 120,
            },
            {
                "sku": "TABLET-DRAW-006",
                "name": "ArtPad Pro Drawing Tablet",
                "description": "10x6\" professional drawing tablet with 8192 levels of pressure sensitivity, tilt support, and wireless connectivity.",
                "price": 15999.00,
                "image_url": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=400",
                "qty": 30,
            },
            {
                "sku": "WEBCAM-HD-007",
                "name": "ClearSight 4K Webcam",
                "description": "4K Ultra HD webcam with auto-focus, built-in ring light, dual noise-cancelling microphones, and privacy shutter.",
                "price": 5499.00,
                "image_url": "https://images.unsplash.com/photo-1587826080692-f439cd0b70da?w=400",
                "qty": 60,
            },
            {
                "sku": "SPEAKER-BT-008",
                "name": "BassCore Portable Speaker",
                "description": "Waterproof IP67 Bluetooth speaker with 360° sound, 20-hour battery, and built-in power bank feature.",
                "price": 4499.00,
                "image_url": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=400",
                "qty": 45,
            },
            {
                "sku": "SSD-EXT-009",
                "name": "SpeedVault 2TB External SSD",
                "description": "Portable 2TB NVMe external SSD with USB 3.2 Gen 2, read speeds up to 2000MB/s, shock-resistant aluminum body.",
                "price": 11999.00,
                "image_url": "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=400",
                "qty": 35,
            },
            {
                "sku": "CHARGER-GAN-010",
                "name": "PowerCube 100W GaN Charger",
                "description": "Ultra-compact 100W GaN charger with 3 USB-C + 1 USB-A port. Charges laptop, tablet, and phone simultaneously.",
                "price": 3499.00,
                "image_url": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=400",
                "qty": 100,
            },
            {
                "sku": "STAND-LAPTOP-011",
                "name": "ElevatePro Laptop Stand",
                "description": "Adjustable aluminum laptop stand with ventilation, cable management, and foldable design for portability.",
                "price": 2499.00,
                "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400",
                "qty": 70,
            },
            {
                "sku": "HUB-USB-012",
                "name": "ConnectAll USB-C Hub 12-in-1",
                "description": "Premium USB-C hub with HDMI 4K, 3x USB-A, SD/microSD, Ethernet, VGA, 3.5mm audio, and 100W PD passthrough.",
                "price": 4999.00,
                "image_url": "https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400",
                "qty": 55,
            },
        ]

        for pd in products_data:
            existing = db.query(Product).filter(Product.sku == pd["sku"]).first()
            if not existing:
                product = Product(
                    vendor_id=vendor.user_id,
                    sku=pd["sku"],
                    name=pd["name"],
                    description=pd["description"],
                    price=pd["price"],
                    image_url=pd["image_url"],
                )
                db.add(product)
                db.flush()

                # Create inventory entry in the warehouse
                inv = InventoryLedger(
                    product_id=product.product_id,
                    warehouse_id=wh.warehouse_id,
                    qty_available=pd["qty"],
                    qty_reserved=0,
                )
                db.add(inv)

        db.commit()
        print(f"✅ {len(products_data)} products seeded with inventory.")

        # ── 6. Seed Shipment and Orders for Map ─────────────────────────
        ship = db.query(Shipment).first()
        if not ship:
            ship = Shipment(
                warehouse_id=wh.warehouse_id,
                carrier_name="AWS FastTrack",
                tracking_number="AWS-9812-IN",
                shipping_cost=150.00
            )
            db.add(ship)
            db.flush()
            print(f"✅ Shipment seeded (ID: {ship.shipment_id})")
        
        buyer_email = "buyer@marketplace.com"
        buyer = db.query(User).filter(User.email == buyer_email).first()
        if not buyer:
            buyer = User(
                email=buyer_email,
                password_hash=hash_password("buyer123"),
            )
            db.add(buyer)
            db.flush()
            buyer_role = db.query(Role).filter(Role.role_name == "Buyer").first()
            if buyer_role:
                buyer.roles.append(buyer_role)
            db.flush()

        import uuid
        existing_order = db.query(Order).first()
        if not existing_order:
            o1 = Order(
                buyer_id=buyer.user_id,
                idempotency_key=str(uuid.uuid4()),
                total_amount=5000.0,
                shipment_id=ship.shipment_id,
                delivery_address="Anna Nagar, Chennai, Tamil Nadu",
                latitude=13.0846,
                longitude=80.2101
            )
            o2 = Order(
                buyer_id=buyer.user_id,
                idempotency_key=str(uuid.uuid4()),
                total_amount=1500.0,
                shipment_id=ship.shipment_id,
                delivery_address="T Nagar, Chennai, Tamil Nadu",
                latitude=13.0418,
                longitude=80.2341
            )
            db.add(o1)
            db.add(o2)
            db.commit()
            print("✅ Dummy Orders seeded for the shipment.")

        print("\n🎉 Seed complete! The database is ready.")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
