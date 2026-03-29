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

    # Pipeline
    pipeline_stage: str = Field(default="lead", index=True)  # lead, prospecto, negociacion, cliente, perdido
    deal_value: float = Field(default=0.0)

    # Metadata
    tags: Optional[str] = None          # JSON array: ["vip", "lead"]
    notes: Optional[str] = None         # JSON array: [{"text":"...", "date":"...", "by":"..."}]
    source: str = Field(default="manual")  # manual, shopify, woocommerce, mercadolibre, import

    # Lead scoring
    lead_score: int = Field(default=0)  # 0-100

    # Aggregated stats
    total_orders: int = Field(default=0)
    total_spent: float = Field(default=0.0)
    last_order_date: Optional[datetime] = None
    last_contacted: Optional[datetime] = None

    # Status
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    """A message in the unified inbox (WhatsApp, Email, FB, IG, SMS)."""
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    contact_id: int = Field(index=True, foreign_key="contacts.id")

    channel: str = Field(index=True)  # whatsapp, email, facebook, instagram, sms
    direction: str  # inbound, outbound
    content: str
    subject: Optional[str] = None  # for email
    status: str = Field(default="sent")  # sent, delivered, read, failed
    extra_data: Optional[str] = None  # JSON: message_id, template, etc.

    created_at: datetime = Field(default_factory=datetime.utcnow)


class LeadForm(SQLModel, table=True):
    """Embeddable lead capture form configuration."""
    __tablename__ = "lead_forms"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    name: str
    slug: str = Field(unique=True, index=True)
    fields: str  # JSON: [{"name":"email","label":"Email","type":"email","required":true}]
    redirect_url: Optional[str] = None
    tags: Optional[str] = None  # JSON: tags to auto-apply to captured contacts
    automation_trigger: Optional[str] = None  # fire this event on submission
    is_active: bool = Field(default=True)
    submissions: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Segment(SQLModel, table=True):
    """Saved contact segment/filter for campaigns."""
    __tablename__ = "segments"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    name: str
    description: Optional[str] = None
    filters: str  # JSON: [{"field":"tags","op":"contains","value":"vip"}]
    contact_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
