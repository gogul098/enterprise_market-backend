"""
SQLAlchemy ORM models for the Enterprise Marketplace.

All tables use InnoDB engine to support row-level pessimistic locking (FOR UPDATE).
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, DECIMAL, Text, DateTime, Date, Boolean,
    ForeignKey, UniqueConstraint, Table, func
)
from sqlalchemy.orm import relationship

from backend.database import Base


# ── Association Table: User ↔ Roles (Many-to-Many) ──────────────────────────
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), primary_key=True),
    mysql_engine="InnoDB",
)

# ── Users ────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"mysql_engine": "InnoDB"}

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="joined")
    orders = relationship("Order", back_populates="buyer", lazy="dynamic")


# ── Roles ────────────────────────────────────────────────────────────────────
class Role(Base):
    __tablename__ = "roles"
    __table_args__ = {"mysql_engine": "InnoDB"}

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), unique=True, nullable=False)

    users = relationship("User", secondary=user_roles, back_populates="roles")


# ── Products ─────────────────────────────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"
    __table_args__ = {"mysql_engine": "InnoDB"}

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    vendor_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    sku = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(DECIMAL(10, 2), nullable=False)
    image_url = Column(String(500), nullable=True)

    inventory = relationship("InventoryLedger", back_populates="product", lazy="joined")


# ── Warehouses ───────────────────────────────────────────────────────────────
class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = {"mysql_engine": "InnoDB"}

    warehouse_id = Column(Integer, primary_key=True, autoincrement=True)
    location_name = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=False, default=1000)
    address = Column(String(255), nullable=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)


# ── Inventory Ledger (Critical – locked with FOR UPDATE during checkout) ─────
class InventoryLedger(Base):
    __tablename__ = "inventory_ledger"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_product_warehouse"),
        {"mysql_engine": "InnoDB"},
    )

    ledger_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id", ondelete="CASCADE"), nullable=False)
    qty_available = Column(Integer, nullable=False, default=0)
    qty_reserved = Column(Integer, nullable=False, default=0)

    product = relationship("Product", back_populates="inventory")
    warehouse = relationship("Warehouse")


# ── Shipments ────────────────────────────────────────────────────────────────
class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = {"mysql_engine": "InnoDB"}

    shipment_id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), nullable=False)
    carrier_name = Column(String(100), nullable=False)
    tracking_number = Column(String(100), unique=True, nullable=True)
    shipping_cost = Column(DECIMAL(10, 2), nullable=False, default=0)
    estimated_delivery = Column(DateTime, nullable=True)
    actual_delivery = Column(DateTime, nullable=True)

    warehouse = relationship("Warehouse")


# ── Orders ───────────────────────────────────────────────────────────────────
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"mysql_engine": "InnoDB"}

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    idempotency_key = Column(String(36), unique=True, nullable=False, index=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0)
    global_status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    shipment_id = Column(Integer, ForeignKey("shipments.shipment_id"), nullable=True)
    delivery_address = Column(String(255), nullable=True)
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)

    buyer = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", lazy="joined")


# ── Order Items ──────────────────────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = {"mysql_engine": "InnoDB"}

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(DECIMAL(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")


# ── Audit Logs ───────────────────────────────────────────────────────────────
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"mysql_engine": "InnoDB"}

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Product Reviews ──────────────────────────────────────────────────────────
class ProductReview(Base):
    __tablename__ = "product_reviews"
    __table_args__ = {"mysql_engine": "InnoDB"}

    review_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    star_rating = Column(Integer, nullable=False)
    verified_purchase = Column(Boolean, nullable=False, default=False)
    helpful_votes = Column(Integer, nullable=False, default=0)
    total_votes = Column(Integer, nullable=False, default=0)
    review_headline = Column(String(255), nullable=True)
    review_body = Column(Text, nullable=False)
    ai_sentiment_score = Column(DECIMAL(3, 2), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    product_quality_rating = Column(Integer, nullable=False, default=5)
    logistics_quality_rating = Column(Integer, nullable=False, default=5)

    product = relationship("Product")
    buyer = relationship("User")


# ── AI Ecosystem Models ──────────────────────────────────────────────────────

class Vendor(Base):
    __tablename__ = "vendor"
    __table_args__ = {"mysql_engine": "InnoDB"}

    vendor_id = Column(String(255), primary_key=True)
    vendor_name = Column(String(255), nullable=True)
    performance_score = Column(DECIMAL(5, 2), default=0.00)
    total_reviews = Column(Integer, default=0)
    marketplace = Column(String(10), nullable=True)
    contact_email = Column(String(255), nullable=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())
    warehouse_count = Column(Integer, nullable=True)


class DemandForecast(Base):
    __tablename__ = "demand_forecasts"
    __table_args__ = {"mysql_engine": "InnoDB"}

    forecast_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.warehouse_id"), nullable=False, index=True)
    target_date = Column(Date, nullable=False)
    predicted_demand = Column(Integer, nullable=False)
    confidence_lower_bound = Column(Integer, nullable=True)
    confidence_upper_bound = Column(Integer, nullable=True)
    generated_at = Column(DateTime, server_default=func.now())

    product = relationship("Product")
    warehouse = relationship("Warehouse")

# ── Admin Restrictions ───────────────────────────────────────────────────────
class AdminRestriction(Base):
    __tablename__ = "admin_restrictions"
    __table_args__ = {"mysql_engine": "InnoDB"}

    restriction_id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    restriction_type = Column(String(50), nullable=False) # e.g., "banned", "vendor_suspended"
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)

    admin = relationship("User", foreign_keys=[admin_id])
    target_user = relationship("User", foreign_keys=[target_user_id])

