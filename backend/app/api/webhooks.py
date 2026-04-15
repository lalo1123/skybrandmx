"""Webhook handlers for external platform integrations."""
import json
from datetime import datetime
from fastapi import APIRouter, Header, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Any
from ..core.database import get_db
from ..models.order import Order

router = APIRouter()


class ShopifyCustomer(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None


class ShopifyOrderWebhook(BaseModel):
    id: int
    email: Optional[str] = None
    total_price: float
    currency: str = "MXN"
    financial_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    customer: Optional[dict] = None
    line_items: Optional[list] = None
    created_at: Optional[str] = None


@router.post("/orders/shopify")
async def shopify_webhook(
    webhook_data: ShopifyOrderWebhook,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Receive order webhooks from Shopify."""
    # Map line items
    items = []
    if webhook_data.line_items:
        for li in webhook_data.line_items:
            items.append({
                "name": li.get("title", ""),
                "qty": li.get("quantity", 1),
                "price": float(li.get("price", 0)),
            })

    customer_name = "N/A"
    if webhook_data.customer:
        first = webhook_data.customer.get("first_name", "")
        last = webhook_data.customer.get("last_name", "")
        customer_name = f"{first} {last}".strip() or "N/A"

    # Auto-generate order number
    max_id = db.query(Order.id).order_by(Order.id.desc()).first()
    next_num = (max_id[0] + 1) if max_id else 1

    new_order = Order(
        workspace_id=1,  # TODO: derive from webhook auth
        order_number=f"SHP-{next_num:03d}",
        customer_name=customer_name,
        customer_email=webhook_data.email,
        items=json.dumps(items) if items else None,
        total=webhook_data.total_price,
        subtotal=webhook_data.total_price,
        status=webhook_data.financial_status or "new",
        payment_method="shopify",
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return {"status": "success", "message": "Pedido sincronizado desde Shopify."}
