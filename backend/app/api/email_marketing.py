"""
Email Marketing API — SkyBrandMX
Campaigns, templates, audiences, subscribers, send, track
"""
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.deps import get_current_user, get_db
from app.models.base import User
from app.models.email_marketing import (
    Campaign, EmailTemplate, Audience, Subscriber, EmailEvent, Suppression
)
from app.integrations.resend_service import get_resend_client, build_email_html

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════ SCHEMAS ═══════

class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(default="promotional")
    subject: str = Field(..., max_length=300)
    preheader: Optional[str] = None
    html_content: Optional[str] = None

class TemplateResponse(BaseModel):
    id: int; name: str; category: str; subject: str; preheader: Optional[str]; uses_count: int; created_at: Optional[datetime]
    class Config: from_attributes = True

class AudienceCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    source: str = Field(default="manual")

class AudienceResponse(BaseModel):
    id: int; name: str; description: Optional[str]; source: str; subscriber_count: int; created_at: Optional[datetime]
    class Config: from_attributes = True

class SubscriberCreate(BaseModel):
    email: str = Field(..., max_length=255)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tags: Optional[list] = None

class CampaignCreate(BaseModel):
    name: str = Field(..., max_length=200)
    subject: str = Field(..., max_length=300)
    preheader: Optional[str] = None
    from_name: str = Field(default="SkyBrandMX")
    from_email: str = Field(default="hola@skybrandmx.com")
    reply_to: Optional[str] = None
    template_id: Optional[int] = None
    audience_id: Optional[int] = None
    scheduled_at: Optional[str] = None
    utm_source: str = Field(default="email")
    utm_medium: str = Field(default="campaign")
    utm_campaign: Optional[str] = None

class CampaignResponse(BaseModel):
    id: int; name: str; subject: str; status: str; from_name: str; from_email: str
    total_sent: int; total_opened: int; total_clicked: int; total_bounced: int; total_unsubscribed: int
    audience_id: Optional[int]; template_id: Optional[int]; scheduled_at: Optional[datetime]; sent_at: Optional[datetime]
    created_at: Optional[datetime]
    class Config: from_attributes = True

class SendTestRequest(BaseModel):
    to: str = Field(..., max_length=255)
    subject: Optional[str] = None

class EmailStats(BaseModel):
    total_campaigns: int = 0
    total_sent: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    total_subscribers: int = 0
    bounce_rate: float = 0.0
    unsubscribe_count: int = 0


# ═══════ TEMPLATES ═══════

@router.post("/templates", response_model=TemplateResponse)
async def create_template(data: TemplateCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = EmailTemplate(workspace_id=user.workspace_id, **data.dict())
    db.add(tpl); db.commit(); db.refresh(tpl)
    return tpl

@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(category: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(EmailTemplate).filter(EmailTemplate.workspace_id == user.workspace_id, EmailTemplate.is_active == True)
    if category: q = q.filter(EmailTemplate.category == category)
    return q.order_by(EmailTemplate.created_at.desc()).all()

@router.delete("/templates/{tpl_id}")
async def delete_template(tpl_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tpl = db.query(EmailTemplate).filter(EmailTemplate.id == tpl_id, EmailTemplate.workspace_id == user.workspace_id).first()
    if not tpl: raise HTTPException(404, "Plantilla no encontrada")
    tpl.is_active = False; db.commit()
    return {"status": "success", "message": "Plantilla eliminada"}


# ═══════ AUDIENCES ═══════

@router.post("/audiences", response_model=AudienceResponse)
async def create_audience(data: AudienceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    aud = Audience(workspace_id=user.workspace_id, **data.dict())
    db.add(aud); db.commit(); db.refresh(aud)
    return aud

@router.get("/audiences", response_model=List[AudienceResponse])
async def list_audiences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Audience).filter(Audience.workspace_id == user.workspace_id, Audience.is_active == True).all()

@router.delete("/audiences/{aud_id}")
async def delete_audience(aud_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    aud = db.query(Audience).filter(Audience.id == aud_id, Audience.workspace_id == user.workspace_id).first()
    if not aud: raise HTTPException(404, "Audiencia no encontrada")
    aud.is_active = False; db.commit()
    return {"status": "success", "message": "Audiencia eliminada"}


# ═══════ SUBSCRIBERS ═══════

@router.post("/audiences/{aud_id}/subscribers")
async def add_subscriber(aud_id: int, data: SubscriberCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    aud = db.query(Audience).filter(Audience.id == aud_id, Audience.workspace_id == user.workspace_id).first()
    if not aud: raise HTTPException(404, "Audiencia no encontrada")
    # Check suppression
    suppressed = db.query(Suppression).filter(Suppression.workspace_id == user.workspace_id, Suppression.email == data.email).first()
    if suppressed: raise HTTPException(400, f"Email {data.email} está en la lista de bloqueados")
    # Check duplicate
    existing = db.query(Subscriber).filter(Subscriber.audience_id == aud_id, Subscriber.email == data.email).first()
    if existing: raise HTTPException(400, f"Email {data.email} ya está en esta audiencia")
    sub = Subscriber(workspace_id=user.workspace_id, audience_id=aud_id, **data.dict())
    db.add(sub)
    aud.subscriber_count += 1
    db.commit(); db.refresh(sub)
    return {"status": "success", "subscriber_id": sub.id, "email": sub.email}

@router.get("/audiences/{aud_id}/subscribers")
async def list_subscribers(aud_id: int, limit: int = Query(50, le=200), offset: int = 0, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    subs = db.query(Subscriber).filter(Subscriber.audience_id == aud_id, Subscriber.workspace_id == user.workspace_id, Subscriber.status == "active").offset(offset).limit(limit).all()
    return [{"id": s.id, "email": s.email, "first_name": s.first_name, "last_name": s.last_name, "status": s.status} for s in subs]

@router.delete("/audiences/{aud_id}/subscribers/{sub_id}")
async def remove_subscriber(aud_id: int, sub_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscriber).filter(Subscriber.id == sub_id, Subscriber.audience_id == aud_id, Subscriber.workspace_id == user.workspace_id).first()
    if not sub: raise HTTPException(404, "Suscriptor no encontrado")
    sub.status = "unsubscribed"
    aud = db.query(Audience).filter(Audience.id == aud_id).first()
    if aud and aud.subscriber_count > 0: aud.subscriber_count -= 1
    db.commit()
    return {"status": "success", "message": f"{sub.email} removido"}


# ═══════ CAMPAIGNS ═══════

@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(data: CampaignCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    camp = Campaign(
        workspace_id=user.workspace_id,
        name=data.name, subject=data.subject, preheader=data.preheader,
        from_name=data.from_name, from_email=data.from_email, reply_to=data.reply_to,
        template_id=data.template_id, audience_id=data.audience_id,
        status="scheduled" if data.scheduled_at else "draft",
        utm_source=data.utm_source, utm_medium=data.utm_medium, utm_campaign=data.utm_campaign or data.name,
    )
    if data.scheduled_at:
        try: camp.scheduled_at = datetime.fromisoformat(data.scheduled_at)
        except: pass
    db.add(camp); db.commit(); db.refresh(camp)
    return camp

@router.get("/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(status: Optional[str] = None, limit: int = Query(50, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Campaign).filter(Campaign.workspace_id == user.workspace_id)
    if status: q = q.filter(Campaign.status == status)
    return q.order_by(Campaign.created_at.desc()).limit(limit).all()

@router.get("/campaigns/{camp_id}", response_model=CampaignResponse)
async def get_campaign(camp_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    camp = db.query(Campaign).filter(Campaign.id == camp_id, Campaign.workspace_id == user.workspace_id).first()
    if not camp: raise HTTPException(404, "Campaña no encontrada")
    return camp

@router.post("/campaigns/{camp_id}/send")
async def send_campaign(camp_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send campaign to all subscribers in the audience"""
    camp = db.query(Campaign).filter(Campaign.id == camp_id, Campaign.workspace_id == user.workspace_id).first()
    if not camp: raise HTTPException(404, "Campaña no encontrada")
    if camp.status == "sent": raise HTTPException(400, "Esta campaña ya fue enviada")
    if not camp.audience_id: raise HTTPException(400, "La campaña no tiene audiencia asignada")

    # Get subscribers
    subs = db.query(Subscriber).filter(
        Subscriber.audience_id == camp.audience_id,
        Subscriber.workspace_id == user.workspace_id,
        Subscriber.status == "active",
    ).all()
    if not subs: raise HTTPException(400, "La audiencia no tiene suscriptores activos")

    # Check suppression list
    suppressed = {s.email for s in db.query(Suppression).filter(Suppression.workspace_id == user.workspace_id).all()}
    valid_subs = [s for s in subs if s.email not in suppressed]

    camp.status = "sending"
    db.commit()

    # Send via Resend
    client = get_resend_client(user.workspace_id, db)
    sent_count = 0
    error_count = 0

    # Get template HTML
    html_body = f"<h2>{camp.subject}</h2><p>Contenido de la campaña</p>"
    if camp.template_id:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        if tpl and tpl.html_content:
            html_body = tpl.html_content

    full_html = build_email_html(camp.subject, html_body)
    from_addr = f"{camp.from_name} <{camp.from_email}>"

    # Send in batches of 50
    for i in range(0, len(valid_subs), 50):
        batch = valid_subs[i:i+50]
        for sub in batch:
            # Personalize
            personalized = full_html.replace("{{nombre}}", sub.first_name or "").replace("{{email}}", sub.email)
            personalized_subject = camp.subject.replace("{{nombre}}", sub.first_name or "")

            result = await client.send_email(
                from_email=from_addr,
                to=sub.email,
                subject=personalized_subject,
                html=personalized,
                reply_to=camp.reply_to,
            )

            if result.get("error"):
                error_count += 1
                event = EmailEvent(workspace_id=user.workspace_id, campaign_id=camp.id, subscriber_email=sub.email, event_type="bounced")
                db.add(event)
            else:
                sent_count += 1
                event = EmailEvent(workspace_id=user.workspace_id, campaign_id=camp.id, subscriber_email=sub.email, event_type="sent")
                db.add(event)

    camp.status = "sent"
    camp.sent_at = datetime.utcnow()
    camp.total_sent = sent_count
    camp.total_bounced = error_count

    # Update template usage
    if camp.template_id:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        if tpl: tpl.uses_count += 1

    db.commit()

    return {
        "status": "success",
        "message": f"Campaña enviada a {sent_count} suscriptores",
        "sent": sent_count,
        "errors": error_count,
        "total_audience": len(valid_subs),
    }


@router.post("/campaigns/{camp_id}/test")
async def send_test_email(camp_id: int, data: SendTestRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send test email to a single address"""
    camp = db.query(Campaign).filter(Campaign.id == camp_id, Campaign.workspace_id == user.workspace_id).first()
    if not camp: raise HTTPException(404, "Campaña no encontrada")

    client = get_resend_client(user.workspace_id, db)
    subject = data.subject or f"[PRUEBA] {camp.subject}"
    html = build_email_html(subject, f"<h2>{camp.subject}</h2><p>Este es un email de prueba.</p>")
    from_addr = f"{camp.from_name} <{camp.from_email}>"

    result = await client.send_email(from_email=from_addr, to=data.to, subject=subject, html=html)
    if result.get("error"):
        raise HTTPException(400, f"Error al enviar: {result.get('detail', {}).get('message', 'Error')}")

    return {"status": "success", "message": f"Email de prueba enviado a {data.to}"}

@router.delete("/campaigns/{camp_id}")
async def delete_campaign(camp_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    camp = db.query(Campaign).filter(Campaign.id == camp_id, Campaign.workspace_id == user.workspace_id).first()
    if not camp: raise HTTPException(404, "Campaña no encontrada")
    db.delete(camp); db.commit()
    return {"status": "success", "message": "Campaña eliminada"}


# ═══════ SUPPRESSION ═══════

@router.get("/suppression")
async def list_suppression(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": s.id, "email": s.email, "reason": s.reason, "created_at": str(s.created_at)} for s in
            db.query(Suppression).filter(Suppression.workspace_id == user.workspace_id).all()]

@router.post("/suppression")
async def add_suppression(email: str, reason: str = "manual", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Suppression).filter(Suppression.workspace_id == user.workspace_id, Suppression.email == email).first()
    if existing: return {"status": "exists", "message": f"{email} ya está bloqueado"}
    sup = Suppression(workspace_id=user.workspace_id, email=email, reason=reason)
    db.add(sup); db.commit()
    return {"status": "success", "message": f"{email} bloqueado"}

@router.delete("/suppression/{sup_id}")
async def remove_suppression(sup_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sup = db.query(Suppression).filter(Suppression.id == sup_id, Suppression.workspace_id == user.workspace_id).first()
    if not sup: raise HTTPException(404, "No encontrado")
    db.delete(sup); db.commit()
    return {"status": "success", "message": "Email desbloqueado"}


# ═══════ STATS ═══════

@router.get("/stats", response_model=EmailStats)
async def get_email_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wid = user.workspace_id
    camps = db.query(Campaign).filter(Campaign.workspace_id == wid, Campaign.status == "sent").all()
    total_sent = sum(c.total_sent for c in camps)
    total_opened = sum(c.total_opened for c in camps)
    total_clicked = sum(c.total_clicked for c in camps)
    total_bounced = sum(c.total_bounced for c in camps)
    total_unsubs = sum(c.total_unsubscribed for c in camps)
    total_subs = db.query(func.sum(Audience.subscriber_count)).filter(Audience.workspace_id == wid, Audience.is_active == True).scalar() or 0

    return EmailStats(
        total_campaigns=len(camps),
        total_sent=total_sent,
        open_rate=round((total_opened / total_sent * 100) if total_sent > 0 else 0, 1),
        click_rate=round((total_clicked / total_sent * 100) if total_sent > 0 else 0, 1),
        total_subscribers=total_subs,
        bounce_rate=round((total_bounced / total_sent * 100) if total_sent > 0 else 0, 2),
        unsubscribe_count=total_unsubs,
    )


# ═══════ WEBHOOKS (Resend events) ═══════

@router.post("/webhooks/resend")
async def resend_webhook(event: dict, db: Session = Depends(get_db)):
    """Receive Resend webhook events (opens, clicks, bounces, etc.)"""
    event_type = event.get("type", "")
    data = event.get("data", {})
    email = data.get("to", [""])[0] if isinstance(data.get("to"), list) else data.get("to", "")

    # Map Resend event types
    type_map = {
        "email.delivered": "delivered",
        "email.opened": "opened",
        "email.clicked": "clicked",
        "email.bounced": "bounced",
        "email.complained": "complained",
    }

    mapped_type = type_map.get(event_type)
    if not mapped_type or not email:
        return {"status": "ignored"}

    # Find the campaign (by resend email ID or recent campaign)
    # For now, log all events
    logger.info(f"Resend webhook: {mapped_type} for {email}")
    return {"status": "received", "type": mapped_type, "email": email}
