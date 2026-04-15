"""
Orders API — SkyBrandMX
Pedidos, devoluciones, estadísticas
"""
import json
import logging
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.deps import get_current_user, get_db
from app.models.base import User
from app.models.order import Order, OrderReturn
from app.schemas.order_schemas import (
    OrderCreate, OrderUpdate, OrderResponse,
    ReturnCreate, ReturnResponse, OrderStats,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════ STATS ═══════

@router.get("/stats", response_model=OrderStats)
async def get_order_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get order dashboard stats"""
    wid = user.workspace_id
    today_start = datetime.combine(date.today(), datetime.min.time())
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_orders = db.query(func.count(Order.id)).filter(
        Order.workspace_id == wid,
    ).scalar() or 0

    orders_today = db.query(func.count(Order.id)).filter(
        Order.workspace_id == wid,
        Order.created_at >= today_start,
    ).scalar() or 0

    month_revenue = db.query(func.coalesce(func.sum(Order.total), 0.0)).filter(
        Order.workspace_id == wid,
        Order.status != "cancelled",
        Order.created_at >= month_start,
    ).scalar() or 0.0

    avg_ticket = db.query(func.avg(Order.total)).filter(
        Order.workspace_id == wid,
        Order.status != "cancelled",
        Order.total > 0,
    ).scalar() or 0.0

    pending_shipping = db.query(func.count(Order.id)).filter(
        Order.workspace_id == wid,
        Order.status.in_(["paid", "preparing"]),
    ).scalar() or 0

    returns_count = db.query(func.count(OrderReturn.id)).filter(
        OrderReturn.workspace_id == wid,
    ).scalar() or 0

    return OrderStats(
        orders_today=orders_today,
        month_revenue=round(month_revenue, 2),
        avg_ticket=round(avg_ticket, 2),
        pending_shipping=pending_shipping,
        returns_count=returns_count,
        total_orders=total_orders,
    )


# ═══════ LIST ORDERS ═══════

@router.get("/", response_model=List[OrderResponse])
async def list_orders(
    search: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: Optional[str] = Query(default="newest", pattern="^(newest|oldest|total_high|total_low)$"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List orders with filters"""
    q = db.query(Order).filter(Order.workspace_id == user.workspace_id)

    if search:
        term = f"%{search}%"
        q = q.filter(
            (Order.customer_name.ilike(term)) | (Order.order_number.ilike(term))
        )
    if status:
        q = q.filter(Order.status == status)
    if date_from:
        q = q.filter(Order.created_at >= date_from)
    if date_to:
        q = q.filter(Order.created_at <= date_to)

    if sort == "oldest":
        q = q.order_by(Order.created_at.asc())
    elif sort == "total_high":
        q = q.order_by(Order.total.desc())
    elif sort == "total_low":
        q = q.order_by(Order.total.asc())
    else:
        q = q.order_by(Order.created_at.desc())

    return q.offset(offset).limit(limit).all()


# ═══════ GET ORDER ═══════

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single order detail"""
    order = db.query(Order).filter(
        Order.id == order_id, Order.workspace_id == user.workspace_id
    ).first()
    if not order:
        raise HTTPException(404, "Pedido no encontrado")
    return order


# ═══════ CREATE ORDER ═══════

@router.post("/", response_model=OrderResponse)
async def create_order(
    data: OrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new order with auto-generated order number"""
    # Auto-generate order number
    max_id = db.query(func.max(Order.id)).filter(
        Order.workspace_id == user.workspace_id,
    ).scalar() or 0
    next_num = max_id + 1
    order_number = f"SKY-{next_num:03d}"

    # Calculate financials from items
    subtotal = 0.0
    items_json = None
    if data.items:
        subtotal = sum(item.qty * item.price for item in data.items)
        items_json = json.dumps(
            [item.model_dump() for item in data.items], ensure_ascii=False
        )

    tax = round(subtotal * 0.16, 2)  # IVA 16%
    total = round(subtotal + tax - data.discount, 2)

    order = Order(
        workspace_id=user.workspace_id,
        order_number=order_number,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        customer_phone=data.customer_phone,
        customer_address=data.customer_address,
        items=items_json,
        subtotal=round(subtotal, 2),
        tax=tax,
        discount=data.discount,
        total=total,
        status="new",
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# ═══════ UPDATE ORDER ═══════

@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    data: OrderUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update order — partial, only non-None fields"""
    order = db.query(Order).filter(
        Order.id == order_id, Order.workspace_id == user.workspace_id
    ).first()
    if not order:
        raise HTTPException(404, "Pedido no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Handle items recalculation
    if "items" in update_data and update_data["items"] is not None:
        items_list = update_data.pop("items")
        subtotal = sum(item.qty * item.price for item in data.items)
        order.items = json.dumps(
            [item.model_dump() for item in data.items], ensure_ascii=False
        )
        order.subtotal = round(subtotal, 2)
        order.tax = round(subtotal * 0.16, 2)
        discount = update_data.get("discount", order.discount)
        order.total = round(order.subtotal + order.tax - discount, 2)
    elif "discount" in update_data:
        discount = update_data.pop("discount")
        order.discount = discount
        order.total = round(order.subtotal + order.tax - discount, 2)

    for key, val in update_data.items():
        setattr(order, key, val)

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


# ═══════ CHANGE STATUS ═══════

class StatusChange(BaseModel):
    status: str

@router.put("/{order_id}/status", response_model=OrderResponse)
async def change_order_status(
    order_id: int,
    data: StatusChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change order status"""
    valid_statuses = {"new", "paid", "preparing", "shipped", "delivered", "cancelled"}
    if data.status not in valid_statuses:
        raise HTTPException(400, f"Estado no válido. Opciones: {', '.join(sorted(valid_statuses))}")

    order = db.query(Order).filter(
        Order.id == order_id, Order.workspace_id == user.workspace_id
    ).first()
    if not order:
        raise HTTPException(404, "Pedido no encontrado")

    order.status = data.status
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


# ═══════ LIST RETURNS ═══════

@router.get("/returns", response_model=List[ReturnResponse])
async def list_returns(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List returns for workspace"""
    return (
        db.query(OrderReturn)
        .filter(OrderReturn.workspace_id == user.workspace_id)
        .order_by(OrderReturn.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ═══════ CREATE RETURN ═══════

@router.post("/returns", response_model=ReturnResponse)
async def create_return(
    data: ReturnCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a return for an existing order"""
    order = db.query(Order).filter(
        Order.id == data.order_id, Order.workspace_id == user.workspace_id
    ).first()
    if not order:
        raise HTTPException(404, "Pedido no encontrado")

    ret = OrderReturn(
        workspace_id=user.workspace_id,
        order_id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        product=data.product,
        reason=data.reason,
        status="requested",
        amount=data.amount,
    )
    db.add(ret)
    db.commit()
    db.refresh(ret)
    return ret
