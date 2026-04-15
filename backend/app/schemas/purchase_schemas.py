"""Pydantic schemas for Purchases API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    rfc: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    rfc: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    rfc: Optional[str]
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    payment_terms: Optional[str]
    year_total: float
    balance: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class POItemInput(BaseModel):
    name: str
    qty: int = 1
    price: float = 0.0


class PurchaseOrderCreate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: str
    items: list[POItemInput] = []
    expected_date: Optional[str] = None
    notes: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    id: int
    workspace_id: int
    folio: str
    supplier_id: Optional[int]
    supplier_name: str
    items: Optional[str]
    subtotal: float
    tax: float
    total: float
    status: str
    expected_date: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    date: str
    description: str
    category: str
    amount: float
    supplier_id: Optional[int] = None


class ExpenseResponse(BaseModel):
    id: int
    workspace_id: int
    date: str
    description: str
    category: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierInvoiceCreate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: str
    folio: str
    rfc: Optional[str] = None
    date: str
    total: float
    status: str = "pending"


class SupplierInvoiceResponse(BaseModel):
    id: int
    workspace_id: int
    folio: str
    supplier_id: Optional[int]
    supplier_name: str
    rfc: Optional[str]
    date: str
    total: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PurchaseStats(BaseModel):
    month_expenses: float
    pending_payment: float
    active_suppliers: int
    pending_orders: int
