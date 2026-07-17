"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from decimal import Decimal


# ── Auth Schemas ─────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "Buyer"  # Accepts "Buyer", "Vendor", "Admin", "Logistics", or "Warehouse"
    address: Optional[str] = None
    vendor_name: Optional[str] = None
    logistics_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: int
    email: str
    roles: List[str]
    access_token: str
    token_type: str = "bearer"


# ── Product Schemas ──────────────────────────────────────────────────────────
class ProductOut(BaseModel):
    product_id: int
    sku: str
    name: str
    description: Optional[str] = None
    price: Decimal
    image_url: Optional[str] = None
    qty_available: int = 0

    class Config:
        from_attributes = True


# ── Checkout Schemas ─────────────────────────────────────────────────────────
class CheckoutItem(BaseModel):
    product_id: int
    quantity: int


class CheckoutRequest(BaseModel):
    buyer_id: int
    idempotency_key: str
    items: List[CheckoutItem]


class OrderItemOut(BaseModel):
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: Decimal

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    order_id: int
    buyer_id: int
    buyer_email: Optional[str] = None
    idempotency_key: str
    total_amount: Decimal
    global_status: str
    created_at: Optional[str] = None
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


# ── Order Status Update ─────────────────────────────────────────────────────
class OrderStatusUpdate(BaseModel):
    status: str  # "pending", "packed", "in_transit", "delivered"

# ── Review Schemas ───────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    buyer_id: int
    product_id: int
    star_rating: int
    review_headline: Optional[str] = None
    review_body: str
    product_quality_rating: int = 5
    logistics_quality_rating: int = 5


class ReviewOut(BaseModel):
    review_id: int
    product_id: int
    buyer_id: int
    star_rating: int
    verified_purchase: bool
    helpful_votes: int
    total_votes: int
    review_headline: Optional[str] = None
    review_body: str
    ai_sentiment_score: Optional[Decimal] = None
    created_at: Optional[str] = None
    product_quality_rating: int
    logistics_quality_rating: int

    class Config:
        from_attributes = True


# ── AI Ecosystem Schemas ─────────────────────────────────────────────────────

class VendorPerformanceOut(BaseModel):
    vendor_id: str
    vendor_name: Optional[str] = None
    performance_score: Optional[float] = None
    letter_grade: str
    warehouse_count: Optional[int] = None


class DemandForecastOut(BaseModel):
    product_id: int
    sku: str
    name: str
    current_stock: int
    velocity_daily: float
    days_remaining: int
    recommendation: str


class InventoryPlanningOut(BaseModel):
    product_id: int
    sku: str
    name: str
    warehouse: str
    qty_available: int
    qty_reserved: int
    reorder_point: int
    status: str


class SentimentReviewOut(BaseModel):
    star_rating: int
    review_body: str
    ai_sentiment_score: Optional[float] = None

class SentimentAnalysisOut(BaseModel):
    product_id: int
    name: str
    average_sentiment: float
    total_reviews: int
    positive_ratio: float
    negative_ratio: float
    recent_reviews: List[SentimentReviewOut]


class AddStockRequest(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: int


class AddStockResponse(BaseModel):
    product_id: int
    warehouse_id: int
    new_qty_available: int
    message: str


class VendorSetupRequest(BaseModel):
    warehouse_count: int


class AddProductRequest(BaseModel):
    name: str
    sku: str
    price: float
    description: Optional[str] = None
    warehouse_id: int = 1
    initial_qty: int = 0
