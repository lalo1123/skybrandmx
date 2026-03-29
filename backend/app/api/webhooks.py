from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Any
from ..schemas.schemas import ShopifyOrderWebhook, GenericResponse
from ..models.models import Order
from ..core.database import get_db # Placeholder for DB dependency

router = APIRouter()

@router.post("/orders/shopify", response_model=GenericResponse)
async def shopify_webhook(
    webhook_data: ShopifyOrderWebhook,
    x_shopify_hmac_sha256: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Receives order webhooks from Shopify and unifies them in the SQL Database.
    Includes basic validation and mapping to the centralized 'orders' table.
    """
    # 1. TODO: Verify Shopify HMAC for security
    
    # 2. Map data to internal Order model
    new_order = Order(
        external_order_id=str(webhook_data.id),
        customer_email=webhook_data.email,
        customer_name=webhook_data.customer.get("first_name", "") if webhook_data.customer else "N/A",
        total_amount=webhook_data.total_price,
        currency=webhook_data.currency,
        payment_status=webhook_data.financial_status,
        fulfillment_status=webhook_data.fulfillment_status or "pending",
        order_date=webhook_data.created_at
    )
    
    # 3. Save to DB
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # 4. TRIGGER ORCHESTRATION (The SaaS Compuesto Magic)
    # We don't make the user wait; we trigger the chain of integrations
    from ..engine.orchestrator import AutomationEngine
    
    orchestration_result = await AutomationEngine.process_event(
        event_type="order.created",
        data=webhook_data.dict(),
        user_id=1, # Simulated user_id
        db=db
    )
    
    return {
        "status": "success", 
        "message": "Order synchronized and orchestration triggered.",
        "data": orchestration_result
    }
