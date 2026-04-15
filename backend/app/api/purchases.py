"""
Purchases API — SkyBrandMX
Suppliers, Purchase Orders, Expenses, Supplier Invoices
"""
import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.deps import get_current_user, get_db
from app.models.base import User
from app.models.purchase import Supplier, PurchaseOrder, Expense, SupplierInvoice
from app.schemas.purchase_schemas import (
    SupplierCreate, SupplierUpdate, SupplierResponse,
    PurchaseOrderCreate, PurchaseOrderResponse,
    ExpenseCreate, ExpenseResponse,
    SupplierInvoiceCreate, SupplierInvoiceResponse,
    PurchaseStats,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════
# STATS
# ═══════════════════════════════════════

@router.get("/stats", response_model=PurchaseStats)
async def purchase_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dashboard stats for purchases module."""
    wid = user.workspace_id
    now = datetime.utcnow()
    year = now.year
    month = now.month

    # Current month prefix for date string filtering (YYYY-MM)
    month_prefix = f"{year}-{month:02d}"

    # Month expenses: sum of expenses in current month
    month_expenses_total = (
        db.query(func.coalesce(func.sum(Expense.amount), 0.0))
        .filter(Expense.workspace_id == wid, Expense.date.like(f"{month_prefix}%"))
        .scalar()
    )

    # Also add paid supplier invoices this month
    paid_invoices_total = (
        db.query(func.coalesce(func.sum(SupplierInvoice.total), 0.0))
        .filter(
            SupplierInvoice.workspace_id == wid,
            SupplierInvoice.status == "paid",
            SupplierInvoice.date.like(f"{month_prefix}%"),
        )
        .scalar()
    )

    month_expenses = float(month_expenses_total) + float(paid_invoices_total)

    # Pending payment: sum of supplier invoices where status = 'pending'
    pending_payment = float(
        db.query(func.coalesce(func.sum(SupplierInvoice.total), 0.0))
        .filter(SupplierInvoice.workspace_id == wid, SupplierInvoice.status == "pending")
        .scalar()
    )

    # Active suppliers
    active_suppliers = (
        db.query(func.count(Supplier.id))
        .filter(Supplier.workspace_id == wid, Supplier.is_active == True)
        .scalar()
    )

    # Pending orders: status in ('draft', 'sent')
    pending_orders = (
        db.query(func.count(PurchaseOrder.id))
        .filter(
            PurchaseOrder.workspace_id == wid,
            PurchaseOrder.status.in_(["draft", "sent"]),
        )
        .scalar()
    )

    return PurchaseStats(
        month_expenses=round(month_expenses, 2),
        pending_payment=round(pending_payment, 2),
        active_suppliers=active_suppliers,
        pending_orders=pending_orders,
    )


# ═══════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════

@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    search: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List suppliers with optional search by name or RFC."""
    wid = user.workspace_id
    q = db.query(Supplier).filter(Supplier.workspace_id == wid, Supplier.is_active == True)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (Supplier.name.ilike(pattern)) | (Supplier.rfc.ilike(pattern))
        )

    return q.order_by(Supplier.name).offset(offset).limit(limit).all()


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single supplier by ID."""
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.workspace_id == user.workspace_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    return supplier


@router.post("/suppliers", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new supplier."""
    supplier = Supplier(
        workspace_id=user.workspace_id,
        name=data.name,
        rfc=data.rfc,
        contact_name=data.contact_name,
        email=data.email,
        phone=data.phone,
        payment_terms=data.payment_terms,
        address=data.address,
        notes=data.notes,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing supplier."""
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.workspace_id == user.workspace_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(supplier, key, value)
    supplier.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a supplier (set is_active=False)."""
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.workspace_id == user.workspace_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")

    supplier.is_active = False
    supplier.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "detail": "Proveedor desactivado."}


# ═══════════════════════════════════════
# PURCHASE ORDERS
# ═══════════════════════════════════════

@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List purchase orders with optional search and status filter."""
    wid = user.workspace_id
    q = db.query(PurchaseOrder).filter(PurchaseOrder.workspace_id == wid)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (PurchaseOrder.folio.ilike(pattern))
            | (PurchaseOrder.supplier_name.ilike(pattern))
        )

    if status:
        q = q.filter(PurchaseOrder.status == status)

    return q.order_by(PurchaseOrder.id.desc()).offset(offset).limit(limit).all()


@router.post("/purchase-orders", response_model=PurchaseOrderResponse)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new purchase order with auto-folio and totals."""
    wid = user.workspace_id

    # Auto-generate folio: OC-001, OC-002, ...
    last_id = (
        db.query(func.max(PurchaseOrder.id))
        .filter(PurchaseOrder.workspace_id == wid)
        .scalar()
        or 0
    )
    folio = f"OC-{last_id + 1:03d}"

    # Calculate totals from items
    subtotal = sum(item.qty * item.price for item in data.items)
    tax = round(subtotal * 0.16, 2)
    total = round(subtotal + tax, 2)

    # Store items as JSON
    items_json = json.dumps(
        [item.model_dump() for item in data.items], ensure_ascii=False
    )

    po = PurchaseOrder(
        workspace_id=wid,
        supplier_id=data.supplier_id,
        folio=folio,
        supplier_name=data.supplier_name,
        items=items_json,
        subtotal=round(subtotal, 2),
        tax=tax,
        total=total,
        expected_date=data.expected_date,
        notes=data.notes,
    )
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


@router.put("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_id: int,
    data: PurchaseOrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a purchase order (recalculates totals)."""
    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.workspace_id == user.workspace_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada.")

    subtotal = sum(item.qty * item.price for item in data.items)
    tax = round(subtotal * 0.16, 2)
    total = round(subtotal + tax, 2)

    items_json = json.dumps(
        [item.model_dump() for item in data.items], ensure_ascii=False
    )

    po.supplier_id = data.supplier_id
    po.supplier_name = data.supplier_name
    po.items = items_json
    po.subtotal = round(subtotal, 2)
    po.tax = tax
    po.total = total
    po.expected_date = data.expected_date
    po.notes = data.notes
    po.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(po)
    return po


@router.put("/purchase-orders/{po_id}/status", response_model=PurchaseOrderResponse)
async def update_po_status(
    po_id: int,
    status: str = Query(..., description="draft, sent, received, paid, cancelled"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the status of a purchase order."""
    valid = {"draft", "sent", "received", "paid", "cancelled"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Opciones: {', '.join(valid)}")

    po = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.id == po_id, PurchaseOrder.workspace_id == user.workspace_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada.")

    po.status = status
    po.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(po)
    return po


# ═══════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════

@router.get("/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List expenses with optional date range and category filter."""
    wid = user.workspace_id
    q = db.query(Expense).filter(Expense.workspace_id == wid)

    if date_from:
        q = q.filter(Expense.date >= date_from)
    if date_to:
        q = q.filter(Expense.date <= date_to)
    if category:
        q = q.filter(Expense.category == category)

    return q.order_by(Expense.date.desc()).offset(offset).limit(limit).all()


@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a new expense."""
    expense = Expense(
        workspace_id=user.workspace_id,
        date=data.date,
        description=data.description,
        category=data.category,
        amount=data.amount,
        supplier_id=data.supplier_id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


# ═══════════════════════════════════════
# SUPPLIER INVOICES (facturas recibidas)
# ═══════════════════════════════════════

@router.get("/invoices/received", response_model=list[SupplierInvoiceResponse])
async def list_supplier_invoices(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List supplier invoices (facturas recibidas)."""
    wid = user.workspace_id
    q = db.query(SupplierInvoice).filter(SupplierInvoice.workspace_id == wid)

    if status:
        q = q.filter(SupplierInvoice.status == status)

    return q.order_by(SupplierInvoice.id.desc()).offset(offset).limit(limit).all()


@router.post("/invoices/received", response_model=SupplierInvoiceResponse)
async def create_supplier_invoice(
    data: SupplierInvoiceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a received supplier invoice."""
    invoice = SupplierInvoice(
        workspace_id=user.workspace_id,
        supplier_id=data.supplier_id,
        folio=data.folio,
        supplier_name=data.supplier_name,
        rfc=data.rfc,
        date=data.date,
        total=data.total,
        status=data.status,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice
