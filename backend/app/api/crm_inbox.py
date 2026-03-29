"""CRM Inbox, Lead Forms, Segments, and Scoring API."""
import json
import uuid
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User
from ..models.crm import Contact, Message, LeadForm, Segment

router = APIRouter()


# ===== UNIFIED INBOX =====

@router.get("/contacts/{contact_id}/messages")
def get_messages(
    contact_id: int,
    channel: str = Query(None),
    limit: int = Query(50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation history for a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    query = db.query(Message).filter(
        Message.contact_id == contact_id,
        Message.workspace_id == current_user.workspace_id,
    )
    if channel:
        query = query.filter(Message.channel == channel)

    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    return [
        {
            "id": m.id,
            "channel": m.channel,
            "direction": m.direction,
            "content": m.content,
            "subject": m.subject,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]


@router.post("/contacts/{contact_id}/send")
def send_message(
    contact_id: int,
    channel: str = Query(..., description="whatsapp, email, sms"),
    content: str = Query(...),
    subject: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to a contact via specified channel."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    sent = False
    error = None

    if channel == "email":
        sent, error = _send_email(contact.email, subject or "Mensaje de SkyBrandMX", content)
    elif channel == "whatsapp":
        # TODO: WhatsApp Cloud API integration
        sent = True  # Stub
    elif channel == "sms":
        # TODO: SMS API integration
        sent = True  # Stub
    else:
        raise HTTPException(400, f"Canal no soportado: {channel}")

    # Save message
    msg = Message(
        workspace_id=current_user.workspace_id,
        contact_id=contact_id,
        channel=channel,
        direction="outbound",
        content=content,
        subject=subject,
        status="sent" if sent else "failed",
    )
    db.add(msg)

    # Update contact
    contact.last_contacted = datetime.utcnow()
    contact.lead_score = min(100, contact.lead_score + 5)
    db.commit()

    return {
        "ok": sent,
        "message_id": msg.id,
        "channel": channel,
        "error": error,
    }


@router.get("/inbox")
def get_inbox(
    channel: str = Query(None),
    limit: int = Query(50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all recent messages across all contacts (unified inbox)."""
    query = db.query(Message).filter(
        Message.workspace_id == current_user.workspace_id,
    )
    if channel:
        query = query.filter(Message.channel == channel)

    messages = query.order_by(Message.created_at.desc()).limit(limit).all()

    result = []
    contact_cache = {}
    for m in messages:
        if m.contact_id not in contact_cache:
            c = db.query(Contact).get(m.contact_id)
            contact_cache[m.contact_id] = c
        c = contact_cache[m.contact_id]

        result.append({
            "id": m.id,
            "channel": m.channel,
            "direction": m.direction,
            "content": m.content[:100],
            "subject": m.subject,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
            "contact": {
                "id": c.id if c else None,
                "name": f"{c.first_name} {c.last_name or ''}" if c else "Desconocido",
                "email": c.email if c else "",
            },
        })

    return result


# ===== LEAD SCORING =====

@router.post("/contacts/{contact_id}/score")
def update_score(
    contact_id: int,
    score: int = Query(..., ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually set a contact's lead score."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    contact.lead_score = score
    contact.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "contact_id": contact_id, "score": score}


@router.post("/contacts/recalculate-scores")
def recalculate_scores(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Auto-calculate lead scores based on activity."""
    contacts = db.query(Contact).filter(
        Contact.workspace_id == current_user.workspace_id,
    ).all()

    updated = 0
    for c in contacts:
        score = 0
        # Has email: +10
        if c.email:
            score += 10
        # Has phone: +10
        if c.phone:
            score += 10
        # Has orders: +5 per order (max 30)
        score += min(30, c.total_orders * 5)
        # Has spent money: +1 per $500 (max 20)
        score += min(20, int(c.total_spent / 500))
        # Active recently: +15 if ordered in last 30 days
        if c.last_order_date and (datetime.utcnow() - c.last_order_date).days < 30:
            score += 15
        # Is in pipeline stage cliente: +10
        if c.pipeline_stage == "cliente":
            score += 10
        elif c.pipeline_stage == "negociacion":
            score += 5
        # Has been contacted: +5
        if c.last_contacted:
            score += 5

        c.lead_score = min(100, score)
        updated += 1

    db.commit()
    return {"ok": True, "contacts_updated": updated}


# ===== LEAD FORMS =====

@router.get("/forms")
def list_forms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all lead capture forms."""
    forms = db.query(LeadForm).filter(
        LeadForm.workspace_id == current_user.workspace_id,
    ).order_by(LeadForm.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "slug": f.slug,
            "fields": json.loads(f.fields) if f.fields else [],
            "tags": json.loads(f.tags) if f.tags else [],
            "is_active": f.is_active,
            "submissions": f.submissions,
            "embed_url": f"/api/v1/crm/forms/{f.slug}/embed",
            "created_at": f.created_at.isoformat(),
        }
        for f in forms
    ]


@router.post("/forms")
def create_form(
    name: str = Query(...),
    fields: str = Query(default='[{"name":"email","label":"Email","type":"email","required":true},{"name":"first_name","label":"Nombre","type":"text","required":true},{"name":"phone","label":"Teléfono","type":"tel","required":false}]'),
    tags: str = Query(default='["lead","formulario"]'),
    redirect_url: str = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new lead capture form."""
    slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"

    form = LeadForm(
        workspace_id=current_user.workspace_id,
        name=name,
        slug=slug,
        fields=fields,
        tags=tags,
        redirect_url=redirect_url,
    )
    db.add(form)
    db.commit()
    db.refresh(form)

    return {
        "id": form.id,
        "name": form.name,
        "slug": form.slug,
        "embed_url": f"/api/v1/crm/forms/{form.slug}/embed",
    }


@router.get("/forms/{slug}/embed")
def get_form_embed(slug: str, db: Session = Depends(get_db)):
    """Get embeddable HTML for a lead form (public endpoint)."""
    form = db.query(LeadForm).filter(LeadForm.slug == slug, LeadForm.is_active == True).first()
    if not form:
        raise HTTPException(404, "Formulario no encontrado")

    fields = json.loads(form.fields) if form.fields else []

    # Generate HTML form
    fields_html = ""
    for f in fields:
        required = "required" if f.get("required") else ""
        fields_html += f'''
        <div style="margin-bottom:12px;">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:4px;color:#374151;">{f["label"]}</label>
            <input type="{f.get("type","text")}" name="{f["name"]}" {required}
                placeholder="{f["label"]}"
                style="width:100%;padding:10px 14px;border:1px solid #e5e7eb;border-radius:8px;font-size:14px;outline:none;" />
        </div>'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"><title>{form.name}</title></head>
<body style="font-family:-apple-system,sans-serif;margin:0;padding:20px;background:#f9fafb;">
<div style="max-width:400px;margin:0 auto;background:#fff;border-radius:16px;padding:28px;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
    <h2 style="font-size:20px;font-weight:800;margin:0 0 16px;color:#111827;">{form.name}</h2>
    <form id="lead-form" action="/api/v1/crm/forms/{slug}/submit" method="POST">
        {fields_html}
        <button type="submit" style="width:100%;padding:12px;background:#084D6E;color:#fff;border:none;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;">
            Enviar
        </button>
    </form>
    <p style="text-align:center;font-size:11px;color:#9ca3af;margin-top:12px;">Powered by SkyBrandMX</p>
</div>
<script>
document.getElementById("lead-form").addEventListener("submit",async(e)=>{{
    e.preventDefault();
    const fd=new FormData(e.target);
    const data=Object.fromEntries(fd);
    const r=await fetch(e.target.action,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}});
    const d=await r.json();
    if(d.ok){{e.target.innerHTML="<p style=\\"text-align:center;font-size:16px;color:#059669;font-weight:700;padding:20px;\\">✓ ¡Gracias! Te contactaremos pronto.</p>";}}
}});
</script>
</body></html>'''

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@router.post("/forms/{slug}/submit")
async def submit_form(
    slug: str,
    data: dict,
    db: Session = Depends(get_db),
):
    """Public endpoint: receive a lead form submission."""
    form = db.query(LeadForm).filter(LeadForm.slug == slug, LeadForm.is_active == True).first()
    if not form:
        raise HTTPException(404, "Formulario no encontrado")

    email = data.get("email", "").strip()
    if not email:
        raise HTTPException(400, "Email es requerido")

    first_name = data.get("first_name") or data.get("nombre") or email.split("@")[0]

    # Check if contact exists
    existing = db.query(Contact).filter(
        Contact.workspace_id == form.workspace_id,
        Contact.email == email,
    ).first()

    form_tags = json.loads(form.tags) if form.tags else ["lead"]

    if existing:
        # Merge tags
        current_tags = json.loads(existing.tags) if existing.tags else []
        merged = list(set(current_tags + form_tags))
        existing.tags = json.dumps(merged)
        existing.updated_at = datetime.utcnow()
        contact_id = existing.id
    else:
        contact = Contact(
            workspace_id=form.workspace_id,
            email=email,
            first_name=first_name,
            last_name=data.get("last_name") or data.get("apellido"),
            phone=data.get("phone") or data.get("telefono"),
            company=data.get("company") or data.get("empresa"),
            tags=json.dumps(form_tags),
            source="formulario",
            pipeline_stage="lead",
            lead_score=25,
        )
        db.add(contact)
        db.flush()
        contact_id = contact.id

    form.submissions += 1
    db.commit()

    # Fire automation if configured
    if form.automation_trigger:
        try:
            from ..engine.runner import fire_event
            await fire_event(
                form.automation_trigger,
                {"contact_id": contact_id, "email": email, "name": first_name, "form": form.name, **data},
                form.workspace_id,
                db,
            )
        except Exception:
            pass

    return {"ok": True, "contact_id": contact_id}


# ===== SEGMENTS =====

@router.get("/segments")
def list_segments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List saved segments."""
    segments = db.query(Segment).filter(
        Segment.workspace_id == current_user.workspace_id,
    ).order_by(Segment.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "filters": json.loads(s.filters) if s.filters else [],
            "contact_count": s.contact_count,
            "created_at": s.created_at.isoformat(),
        }
        for s in segments
    ]


@router.post("/segments")
def create_segment(
    name: str = Query(...),
    description: str = Query(None),
    filters: str = Query(..., description='JSON array of filter conditions'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a saved segment."""
    # Count matching contacts
    filter_list = json.loads(filters)
    query = db.query(Contact).filter(Contact.workspace_id == current_user.workspace_id)

    for f in filter_list:
        field = f.get("field", "")
        op = f.get("op", "eq")
        value = f.get("value", "")

        col = getattr(Contact, field, None)
        if not col:
            continue

        if op == "eq":
            query = query.filter(col == value)
        elif op == "neq":
            query = query.filter(col != value)
        elif op == "contains":
            query = query.filter(col.ilike(f"%{value}%"))
        elif op == "gt":
            query = query.filter(col > float(value))
        elif op == "lt":
            query = query.filter(col < float(value))

    count = query.count()

    segment = Segment(
        workspace_id=current_user.workspace_id,
        name=name,
        description=description,
        filters=filters,
        contact_count=count,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)

    return {"id": segment.id, "name": name, "contact_count": count}


@router.get("/segments/{segment_id}/contacts")
def get_segment_contacts(
    segment_id: int,
    limit: int = Query(50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get contacts matching a segment's filters."""
    segment = db.query(Segment).filter(
        Segment.id == segment_id,
        Segment.workspace_id == current_user.workspace_id,
    ).first()
    if not segment:
        raise HTTPException(404, "Segmento no encontrado")

    filter_list = json.loads(segment.filters) if segment.filters else []
    query = db.query(Contact).filter(Contact.workspace_id == current_user.workspace_id)

    for f in filter_list:
        field = f.get("field", "")
        op = f.get("op", "eq")
        value = f.get("value", "")
        col = getattr(Contact, field, None)
        if not col:
            continue
        if op == "eq":
            query = query.filter(col == value)
        elif op == "neq":
            query = query.filter(col != value)
        elif op == "contains":
            query = query.filter(col.ilike(f"%{value}%"))
        elif op == "gt":
            query = query.filter(col > float(value))
        elif op == "lt":
            query = query.filter(col < float(value))

    contacts = query.limit(limit).all()
    return contacts


# ===== HELPERS =====

def _send_email(to: str, subject: str, body: str) -> tuple[bool, str | None]:
    """Send email via SMTP."""
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.hostinger.com")
        smtp_port = int(os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_USER", "noreply@skybrandmx.com")
        smtp_pass = os.getenv("SMTP_PASSWORD", "")

        msg = MIMEMultipart("alternative")
        msg["From"] = f"SkyBrandMX <{smtp_user}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return True, None
    except Exception as e:
        return False, str(e)
