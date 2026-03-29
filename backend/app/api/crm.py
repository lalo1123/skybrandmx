"""CRM API endpoints — contacts CRUD, import, notes, stats."""
import json
import csv
import io
from datetime import datetime, timedelta
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User
from ..models.crm import Contact
from ..schemas.crm_schemas import (
    ContactCreate, ContactUpdate, ContactResponse,
    NoteCreate, CRMStats,
)

router = APIRouter()


# ===== STATS =====

@router.get("/stats", response_model=CRMStats)
def get_crm_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get CRM dashboard stats."""
    ws = current_user.workspace_id
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total = db.query(Contact).filter(Contact.workspace_id == ws).count()
    active = db.query(Contact).filter(Contact.workspace_id == ws, Contact.is_active == True).count()
    new_week = db.query(Contact).filter(Contact.workspace_id == ws, Contact.created_at >= week_ago).count()
    new_month = db.query(Contact).filter(Contact.workspace_id == ws, Contact.created_at >= month_ago).count()
    total_revenue = db.query(func.sum(Contact.total_spent)).filter(Contact.workspace_id == ws).scalar() or 0

    # Top tags
    contacts = db.query(Contact.tags).filter(Contact.workspace_id == ws, Contact.tags.isnot(None)).all()
    tag_counter = Counter()
    for (tags_json,) in contacts:
        try:
            for tag in json.loads(tags_json):
                tag_counter[tag] += 1
        except (json.JSONDecodeError, TypeError):
            pass
    top_tags = [{"tag": t, "count": c} for t, c in tag_counter.most_common(10)]

    # Sources
    source_rows = (
        db.query(Contact.source, func.count(Contact.id))
        .filter(Contact.workspace_id == ws)
        .group_by(Contact.source)
        .all()
    )
    sources = [{"source": s, "count": c} for s, c in source_rows]

    return CRMStats(
        total_contacts=total,
        active_contacts=active,
        new_this_week=new_week,
        new_this_month=new_month,
        top_tags=top_tags,
        sources=sources,
        total_revenue=total_revenue,
    )


# ===== LIST / SEARCH =====

@router.get("/contacts", response_model=list[ContactResponse])
def list_contacts(
    search: str = Query(None, description="Search by name, email, phone, or company"),
    tag: str = Query(None, description="Filter by tag"),
    source: str = Query(None, description="Filter by source"),
    is_active: bool = Query(None),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List contacts with search, filters, and pagination."""
    query = db.query(Contact).filter(Contact.workspace_id == current_user.workspace_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            Contact.first_name.ilike(search_term),
            Contact.last_name.ilike(search_term),
            Contact.email.ilike(search_term),
            Contact.phone.ilike(search_term),
            Contact.company.ilike(search_term),
        ))

    if tag:
        query = query.filter(Contact.tags.contains(f'"{tag}"'))

    if source:
        query = query.filter(Contact.source == source)

    if is_active is not None:
        query = query.filter(Contact.is_active == is_active)

    # Sort
    sort_col = getattr(Contact, sort, Contact.created_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    contacts = query.offset(offset).limit(limit).all()
    return contacts


# ===== CRUD =====

@router.post("/contacts", response_model=ContactResponse)
def create_contact(
    data: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new contact."""
    existing = db.query(Contact).filter(
        Contact.workspace_id == current_user.workspace_id,
        Contact.email == data.email,
    ).first()
    if existing:
        raise HTTPException(400, f"Ya existe un contacto con email {data.email}")

    contact = Contact(
        workspace_id=current_user.workspace_id,
        email=data.email,
        phone=data.phone,
        first_name=data.first_name,
        last_name=data.last_name,
        company=data.company,
        state=data.state,
        city=data.city,
        address=data.address,
        zip_code=data.zip_code,
        tags=json.dumps(data.tags) if data.tags else None,
        source=data.source,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")
    return contact


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])

    for key, value in update_data.items():
        setattr(contact, key, value)

    contact.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/contacts/{contact_id}")
def delete_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")
    db.delete(contact)
    db.commit()
    return {"ok": True, "message": f"Contacto {contact.first_name} eliminado"}


# ===== NOTES =====

@router.post("/contacts/{contact_id}/notes")
def add_note(
    contact_id: int,
    data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a note to a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.workspace_id == current_user.workspace_id,
    ).first()
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    notes = json.loads(contact.notes) if contact.notes else []
    notes.insert(0, {
        "text": data.text,
        "date": datetime.utcnow().isoformat(),
        "by": current_user.full_name or current_user.email,
    })
    contact.notes = json.dumps(notes)
    contact.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "notes": notes}


# ===== TAGS =====

@router.get("/tags")
def list_tags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tags used in the workspace."""
    contacts = db.query(Contact.tags).filter(
        Contact.workspace_id == current_user.workspace_id,
        Contact.tags.isnot(None),
    ).all()

    tag_counter = Counter()
    for (tags_json,) in contacts:
        try:
            for tag in json.loads(tags_json):
                tag_counter[tag] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    return [{"tag": t, "count": c} for t, c in tag_counter.most_common(50)]


# ===== IMPORT CSV =====

@router.post("/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import contacts from a CSV file."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos .csv")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    created = 0
    updated = 0
    errors = []

    for i, row in enumerate(reader):
        email = (row.get("email") or row.get("Email") or row.get("EMAIL") or "").strip()
        if not email:
            errors.append(f"Fila {i+2}: sin email")
            continue

        first_name = (row.get("first_name") or row.get("nombre") or row.get("Nombre") or row.get("name") or "").strip()
        if not first_name:
            first_name = email.split("@")[0]

        existing = db.query(Contact).filter(
            Contact.workspace_id == current_user.workspace_id,
            Contact.email == email,
        ).first()

        if existing:
            # Update existing
            if row.get("phone") or row.get("telefono") or row.get("Teléfono"):
                existing.phone = (row.get("phone") or row.get("telefono") or row.get("Teléfono") or "").strip()
            if row.get("company") or row.get("empresa") or row.get("Empresa"):
                existing.company = (row.get("company") or row.get("empresa") or row.get("Empresa") or "").strip()
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            contact = Contact(
                workspace_id=current_user.workspace_id,
                email=email,
                first_name=first_name,
                last_name=(row.get("last_name") or row.get("apellido") or row.get("Apellido") or "").strip() or None,
                phone=(row.get("phone") or row.get("telefono") or row.get("Teléfono") or "").strip() or None,
                company=(row.get("company") or row.get("empresa") or row.get("Empresa") or "").strip() or None,
                state=(row.get("state") or row.get("estado") or row.get("Estado") or "").strip() or None,
                city=(row.get("city") or row.get("ciudad") or row.get("Ciudad") or "").strip() or None,
                tags=json.dumps(["importado"]),
                source="import",
            )
            db.add(contact)
            created += 1

    db.commit()

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "errors": errors[:10],
        "message": f"{created} contactos creados, {updated} actualizados" + (f", {len(errors)} errores" if errors else ""),
    }
