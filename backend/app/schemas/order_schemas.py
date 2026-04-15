"""Pydantic schemas for Orders API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OrderItemInput(BaseModel):
    name: str
    qty: int = 1
    price: float = 0.0


class OrderCreate(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    items: list[OrderItemInput] = []
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    discount: float = 0.0


class OrderUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    items: Optional[list[OrderItemInput]] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    tracking_number: Optional[str] = None
    discount: Optional[float] = None


class OrderResponse(BaseModel):
    id: int
    workspace_id: int
    order_number: str
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    customer_address: Optional[str]
    items: Optional[str]  # JSON string
    subtotal: float
    tax: float
    discount: float
    total: float
    status: str
    payment_method: Optional[str]
    tracking_number: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReturnCreate(BaseModel):
    order_id: int
    product: Optional[str] = None
    reason: str
    amount: float = 0.0


class ReturnResponse(BaseModel):
    id: int
    workspace_id: int
    order_id: int
    order_number: str
    customer_name: str
    product: Optional[str]
    reason: str
    status: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class OrderStats(BaseModel):
    orders_today: int
    month_revenue: float
    avg_ticket: float
    pending_shipping: int
    returns_count: int
    total_orders: int
