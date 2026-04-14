"""
Email Marketing models — SkyBrandMX
Campaigns, Templates, Audiences, Subscribers, Tracking
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Column, JSON


class EmailTemplate(SQLModel, table=True):
    """Plantilla de email reutilizable"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str = Field(max_length=200)
    category: str = Field(default="promotional", max_length=30)  # promotional, welcome, newsletter, abandoned, transactional
    subject: str = Field(max_length=300)
    preheader: Optional[str] = Field(default=None, max_length=200)
    html_content: Optional[str] = Field(default=None, sa_column=Column("html_content", JSON))
    blocks: Optional[list] = Field(default=None, sa_column=Column("blocks", JSON))  # Editor blocks
    uses_count: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Audience(SQLModel, table=True):
    """Lista de audiencia / suscriptores"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    source: str = Field(default="manual", max_length=20)  # crm, import, manual, form
    subscriber_count: int = Field(default=0)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Subscriber(SQLModel, table=True):
    """Suscriptor de una audiencia"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    audience_id: int = Field(foreign_key="audience.id", index=True)
    email: str = Field(max_length=255, index=True)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[list] = Field(default=None, sa_column=Column("tags", JSON))
    status: str = Field(default="active", max_length=20)  # active, unsubscribed, bounced, complained
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Campaign(SQLModel, table=True):
    """Campaña de email marketing"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str = Field(max_length=200)
    subject: str = Field(max_length=300)
    preheader: Optional[str] = Field(default=None, max_length=200)
    from_name: str = Field(default="SkyBrandMX", max_length=100)
    from_email: str = Field(default="hola@skybrandmx.com", max_length=255)
    reply_to: Optional[str] = Field(default=None, max_length=255)

    template_id: Optional[int] = Field(default=None, foreign_key="emailtemplate.id")
    audience_id: Optional[int] = Field(default=None, foreign_key="audience.id")

    status: str = Field(default="draft", max_length=20)  # draft, scheduled, sending, sent, cancelled
    scheduled_at: Optional[datetime] = Field(default=None)
    sent_at: Optional[datetime] = Field(default=None)

    # Metrics
    total_sent: int = Field(default=0)
    total_opened: int = Field(default=0)
    total_clicked: int = Field(default=0)
    total_bounced: int = Field(default=0)
    total_unsubscribed: int = Field(default=0)
    total_complained: int = Field(default=0)

    # UTM
    utm_source: str = Field(default="email", max_length=50)
    utm_medium: str = Field(default="campaign", max_length=50)
    utm_campaign: Optional[str] = Field(default=None, max_length=100)

    # Resend
    resend_batch_id: Optional[str] = Field(default=None, max_length=100)

    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class EmailEvent(SQLModel, table=True):
    """Evento de tracking (apertura, clic, rebote, etc.)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    campaign_id: int = Field(foreign_key="campaign.id", index=True)
    subscriber_email: str = Field(max_length=255, index=True)
    event_type: str = Field(max_length=20)  # sent, delivered, opened, clicked, bounced, complained, unsubscribed
    link_url: Optional[str] = Field(default=None, max_length=500)
    user_agent: Optional[str] = Field(default=None, max_length=300)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Suppression(SQLModel, table=True):
    """Email bloqueado / blacklist"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    email: str = Field(max_length=255, index=True)
    reason: str = Field(default="manual", max_length=20)  # manual, bounce, complaint, legal, invalid
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
