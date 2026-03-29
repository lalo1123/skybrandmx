"""Pydantic schemas for CRM API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ContactCreate(BaseModel):
    email: str
    phone: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    company: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    tags: Optional[list[str]] = None
    source: str = "manual"
    pipeline_stage: str = "lead"
    deal_value: float = 0.0


class ContactUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None
    pipeline_stage: Optional[str] = None
    deal_value: Optional[float] = None


class ContactResponse(BaseModel):
    id: int
    workspace_id: int
    email: str
    phone: Optional[str]
    first_name: str
    last_name: Optional[str]
    company: Optional[str]
    state: Optional[str]
    city: Optional[str]
    address: Optional[str]
    zip_code: Optional[str]
    tags: Optional[str]
    notes: Optional[str]
    source: str
    pipeline_stage: str
    deal_value: float
    total_orders: int
    total_spent: float
    last_order_date: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    text: str


class CRMStats(BaseModel):
    total_contacts: int
    active_contacts: int
    new_this_week: int
    new_this_month: int
    top_tags: list[dict]
    sources: list[dict]
    total_revenue: float
