"""Order database models."""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Order(SQLModel, table=True):
    __tablename__ = "order"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    # Order identity
    order_number: str = Field(max_length=20, index=True)  # SKY-001

    # Customer
    customer_name: str = Field(max_length=200)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_phone: Optional[str] = Field(default=None, max_length=20)
    customer_address: Optional[str] = None

    # Items stored as JSON array: [{"name":"...", "qty":2, "price":450}]
    items: Optional[str] = None

    # Financials
    subtotal: float = Field(default=0.0)
    tax: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    total: float = Field(default=0.0)

    # Status: new, paid, preparing, shipped, delivered, cancelled
    status: str = Field(default="new", max_length=20, index=True)

    # Payment: card, oxxo, transfer, cash, pending
    payment_method: Optional[str] = Field(default=None, max_length=20)

    # Shipping
    tracking_number: Optional[str] = Field(default=None, max_length=50)

    # Notes
    notes: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderReturn(SQLModel, table=True):
    __tablename__ = "order_return"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    order_id: int = Field(foreign_key="order.id", index=True)

    order_number: str = Field(max_length=20)
    customer_name: str = Field(max_length=200)
    product: Optional[str] = None  # "Blusa bordada (x1)"
    reason: str = Field(max_length=300)
    status: str = Field(default="requested", max_length=20)  # requested, approved, rejected, completed
    amount: float = Field(default=0.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
