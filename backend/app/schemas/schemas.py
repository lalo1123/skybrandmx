from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime

class ShopifyCustomer(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[EmailStr]

class ShopifyOrderWebhook(BaseModel):
    id: int
    email: EmailStr
    total_price: float
    currency: str
    financial_status: str
    fulfillment_status: Optional[str]
    created_at: datetime
    customer: Optional[Dict[str, Any]]
    line_items: List[Dict[str, Any]]

class GenericResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

class ConnectionPayload(BaseModel):
    provider_slug: str
    api_key: str
    api_secret: Optional[str] = None

class ERPInventorySync(BaseModel):
    sku: str
    quantity: int
    location: Optional[str] = None
