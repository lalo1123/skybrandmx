"""CRM database models."""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Contact(SQLModel, table=True):
    """A customer/lead contact in the CRM."""
    __tablename__ = "contacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    # Identity
    email: str = Field(index=True)
    phone: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    company: Optional[str] = None

    # Location
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None

    # Metadata
    tags: Optional[str] = None          # JSON array: ["vip", "lead"]
    notes: Optional[str] = None         # JSON array: [{"text":"...", "date":"...", "by":"..."}]
    source: str = Field(default="manual")  # manual, shopify, woocommerce, mercadolibre, import

    # Aggregated stats
    total_orders: int = Field(default=0)
    total_spent: float = Field(default=0.0)
    last_order_date: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
