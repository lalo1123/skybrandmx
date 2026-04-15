"""Purchase and Supplier database models."""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    name: str = Field(max_length=255)  # razón social
    rfc: Optional[str] = Field(default=None, max_length=13)
    contact_name: Optional[str] = Field(default=None, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    payment_terms: Optional[str] = Field(default=None, max_length=50)  # "30 días"
    address: Optional[str] = None
    notes: Optional[str] = None

    # Stats
    year_total: float = Field(default=0.0)
    balance: float = Field(default=0.0)

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PurchaseOrder(SQLModel, table=True):
    __tablename__ = "purchase_order"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")

    folio: str = Field(max_length=20, index=True)  # OC-001
    supplier_name: str = Field(max_length=255)

    # Items as JSON: [{"name":"...", "qty":10, "price":100}]
    items: Optional[str] = None

    subtotal: float = Field(default=0.0)
    tax: float = Field(default=0.0)
    total: float = Field(default=0.0)

    # Status: draft, sent, received, paid, cancelled
    status: str = Field(default="draft", max_length=20, index=True)

    expected_date: Optional[str] = None
    notes: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Expense(SQLModel, table=True):
    __tablename__ = "expense"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    date: str = Field(max_length=10)  # YYYY-MM-DD
    description: str = Field(max_length=300)
    category: str = Field(max_length=50)  # Transporte, Viáticos, Servicios, Oficina
    amount: float = Field(default=0.0)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierInvoice(SQLModel, table=True):
    """Received invoice from supplier (factura recibida)."""
    __tablename__ = "supplier_invoice"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")

    folio: str = Field(max_length=50)
    supplier_name: str = Field(max_length=255)
    rfc: Optional[str] = Field(default=None, max_length=13)
    date: str = Field(max_length=10)
    total: float = Field(default=0.0)
    status: str = Field(default="pending", max_length=20)  # pending, paid, partial

    created_at: datetime = Field(default_factory=datetime.utcnow)
