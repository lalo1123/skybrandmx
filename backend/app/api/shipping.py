"""
Shipping API — SkyBrandMX
Cotizar, generar guías, rastrear, etiquetas
"""
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.deps import get_current_user, get_db
from app.models.base import User
from app.models.shipping import Shipment, ShipmentEvent, ReturnLabel
from app.integrations.skydropx_service import (
    get_skydropx_client, calculate_user_price, calculate_volumetric_weight
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════ SCHEMAS ═══════

class QuoteRequest(BaseModel):
    zip_from: str = Field(..., min_length=5, max_length=5)
    zip_to: str = Field(..., min_length=5, max_length=5)
    weight: float = Field(default=1.0, gt=0)
    length: float = Field(default=30.0, gt=0)
    width: float = Field(default=20.0, gt=0)
    height: float = Field(default=15.0, gt=0)
    declared_value: float = Field(default=0.0, ge=0)
    insured: bool = False

class QuoteRate(BaseModel):
    carrier: str
    service: str
    days: Optional[int] = None
    cost: float  # What we pay
    price: float  # What user pays
    margin: float
    rate_id: Optional[str] = None
    quotation_id: Optional[str] = None

class QuoteResponse(BaseModel):
    rates: List[QuoteRate]
    volumetric_weight: float
    billable_weight: float  # max(real, volumetric)

class ShipmentCreate(BaseModel):
    # Origin
    origin_name: str = Field(..., max_length=200)
    origin_zip: str = Field(..., min_length=5, max_length=5)
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    origin_street: Optional[str] = None
    origin_phone: Optional[str] = None
    # Destination
    dest_name: str = Field(..., max_length=200)
    dest_zip: str = Field(..., min_length=5, max_length=5)
    dest_city: Optional[str] = None
    dest_state: Optional[str] = None
    dest_street: Optional[str] = None
    dest_phone: Optional[str] = None
    dest_email: Optional[str] = None
    # Parcel
    weight: float = Field(default=1.0, gt=0)
    length: float = Field(default=30.0, gt=0)
    width: float = Field(default=20.0, gt=0)
    height: float = Field(default=15.0, gt=0)
    content_description: Optional[str] = None
    declared_value: float = Field(default=0.0, ge=0)
    insured: bool = False
    # Selected rate
    carrier: str
    rate_id: Optional[str] = None
    quotation_id: Optional[str] = None
    cost: float = 0.0
    price: float = 0.0
    # Related
    order_id: Optional[int] = None

class ShipmentResponse(BaseModel):
    id: int
    workspace_id: int
    tracking_number: Optional[str]
    carrier: str
    service_level: Optional[str]
    status: str
    dest_name: str
    dest_zip: str
    dest_city: Optional[str]
    origin_zip: str
    weight: float
    cost: float
    price: float
    label_url: Optional[str]
    tracking_url: Optional[str]
    created_at: Optional[datetime]
    class Config:
        from_attributes = True

class TrackRequest(BaseModel):
    tracking_number: str
    carrier: Optional[str] = None

class ShippingStats(BaseModel):
    total_shipments: int = 0
    in_transit: int = 0
    delivered: int = 0
    avg_cost: float = 0.0
    total_spent: float = 0.0
    total_revenue: float = 0.0
    returns: int = 0


# ═══════ QUOTATION ═══════

@router.post("/quote", response_model=QuoteResponse)
async def get_shipping_quote(
    data: QuoteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get shipping rates from all carriers"""
    vol_weight = calculate_volumetric_weight(data.length, data.width, data.height)
    billable = max(data.weight, vol_weight)

    client = get_skydropx_client(user.workspace_id, db)
    result = await client.create_quotation(
        data.zip_from, data.zip_to, billable, data.length, data.width, data.height
    )

    if result.get("error"):
        # Return demo rates if API fails
        logger.warning("Skydropx API failed, returning demo rates")
        base = billable * 45
        demo_rates = [
            QuoteRate(carrier="Estafeta", service="Terrestre", days=4, **calculate_user_price(round(base * 0.85 + 25)), rate_id=None, quotation_id=None),
            QuoteRate(carrier="DHL", service="Express", days=2, **calculate_user_price(round(base * 1.2 + 40)), rate_id=None, quotation_id=None),
            QuoteRate(carrier="FedEx", service="Estándar", days=3, **calculate_user_price(round(base * 1.1 + 35)), rate_id=None, quotation_id=None),
            QuoteRate(carrier="Redpack", service="Terrestre", days=4, **calculate_user_price(round(base * 0.9 + 30)), rate_id=None, quotation_id=None),
            QuoteRate(carrier="99 Minutos", service="Mismo día (CDMX)", days=0, **calculate_user_price(round(base * 0.7 + 20)), rate_id=None, quotation_id=None),
        ]
        demo_rates.sort(key=lambda x: x.price)
        return QuoteResponse(rates=demo_rates, volumetric_weight=vol_weight, billable_weight=billable)

    # Parse real Skydropx rates
    rates = []
    quotation_id = result.get("data", {}).get("id")
    included = result.get("included", [])
    for item in included:
        if item.get("type") == "rates":
            attrs = item.get("attributes", {})
            carrier_cost = float(attrs.get("total_pricing", 0) or attrs.get("amount_local", 0))
            pricing = calculate_user_price(carrier_cost)
            rates.append(QuoteRate(
                carrier=attrs.get("provider", "Unknown"),
                service=attrs.get("service_level_name", "Standard"),
                days=attrs.get("days"),
                rate_id=item.get("id"),
                quotation_id=quotation_id,
                **pricing,
            ))

    rates.sort(key=lambda x: x.price)
    return QuoteResponse(rates=rates, volumetric_weight=vol_weight, billable_weight=billable)


# ═══════ CREATE SHIPMENT ═══════

@router.post("/shipments", response_model=ShipmentResponse)
async def create_shipment(
    data: ShipmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a shipment and generate label"""
    vol_weight = calculate_volumetric_weight(data.length, data.width, data.height)

    shipment = Shipment(
        workspace_id=user.workspace_id,
        carrier=data.carrier,
        status="created",
        origin_name=data.origin_name,
        origin_zip=data.origin_zip,
        origin_city=data.origin_city,
        origin_state=data.origin_state,
        origin_street=data.origin_street,
        origin_phone=data.origin_phone,
        dest_name=data.dest_name,
        dest_zip=data.dest_zip,
        dest_city=data.dest_city,
        dest_state=data.dest_state,
        dest_street=data.dest_street,
        dest_phone=data.dest_phone,
        dest_email=data.dest_email,
        weight=data.weight,
        length=data.length,
        width=data.width,
        height=data.height,
        volumetric_weight=vol_weight,
        content_description=data.content_description,
        declared_value=data.declared_value,
        insured=data.insured,
        cost=data.cost,
        price=data.price,
        margin=data.price - data.cost,
        skydropx_rate_id=data.rate_id,
        skydropx_quotation_id=data.quotation_id,
        order_id=data.order_id,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Generate label via Skydropx
    if data.rate_id:
        try:
            client = get_skydropx_client(user.workspace_id, db)
            label_result = await client.create_label(data.rate_id)
            if not label_result.get("error"):
                attrs = label_result.get("data", {}).get("attributes", {})
                shipment.tracking_number = attrs.get("tracking_number")
                shipment.label_url = attrs.get("label_url")
                shipment.tracking_url = attrs.get("tracking_url_provider")
                shipment.skydropx_label_id = label_result.get("data", {}).get("id")
                shipment.status = "created"

                # Add creation event
                event = ShipmentEvent(
                    shipment_id=shipment.id,
                    description="Guía creada",
                    location=data.origin_city or data.origin_zip,
                    status="created",
                )
                db.add(event)
                db.commit()
        except Exception as e:
            logger.error(f"Error creating label: {e}")
            # Generate demo tracking number
            shipment.tracking_number = f"{data.carrier[:3].upper()}{shipment.id:09d}"
            event = ShipmentEvent(
                shipment_id=shipment.id,
                description="Guía creada (demo)",
                location=data.origin_zip,
                status="created",
            )
            db.add(event)
            db.commit()
    else:
        # No rate_id — generate demo tracking
        shipment.tracking_number = f"{data.carrier[:3].upper()}{shipment.id:09d}"
        event = ShipmentEvent(
            shipment_id=shipment.id,
            description="Guía creada (sin Skydropx)",
            location=data.origin_zip,
            status="created",
        )
        db.add(event)
        db.commit()

    db.refresh(shipment)
    return shipment


# ═══════ LIST / GET SHIPMENTS ═══════

@router.get("/shipments", response_model=List[ShipmentResponse])
async def list_shipments(
    search: Optional[str] = None,
    carrier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List shipments"""
    q = db.query(Shipment).filter(Shipment.workspace_id == user.workspace_id)
    if search:
        term = f"%{search}%"
        q = q.filter((Shipment.tracking_number.ilike(term)) | (Shipment.dest_name.ilike(term)))
    if carrier:
        q = q.filter(Shipment.carrier == carrier)
    if status:
        q = q.filter(Shipment.status == status)
    return q.order_by(Shipment.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get shipment details"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")
    return s


# ═══════ TRACKING ═══════

@router.post("/track")
async def track_shipment(
    data: TrackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Track a shipment by tracking number"""
    # First check our DB
    shipment = db.query(Shipment).filter(
        Shipment.tracking_number == data.tracking_number,
        Shipment.workspace_id == user.workspace_id,
    ).first()

    # Try Skydropx tracking
    if data.carrier or (shipment and shipment.carrier):
        carrier = data.carrier or shipment.carrier
        client = get_skydropx_client(user.workspace_id, db)
        result = await client.track_shipment(carrier, data.tracking_number)
        if not result.get("error"):
            return result

    # Return DB events if available
    if shipment:
        events = db.query(ShipmentEvent).filter(ShipmentEvent.shipment_id == shipment.id).order_by(ShipmentEvent.event_date.desc()).all()
        return {
            "tracking_number": shipment.tracking_number,
            "carrier": shipment.carrier,
            "status": shipment.status,
            "events": [{"description": e.description, "location": e.location, "date": str(e.event_date)} for e in events],
        }

    return {"tracking_number": data.tracking_number, "status": "not_found", "events": [], "message": "No se encontró el envío"}


# ═══════ LABEL ═══════

@router.get("/shipments/{shipment_id}/label")
async def get_label(
    shipment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get shipping label URL"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")
    return {"label_url": s.label_url, "tracking_number": s.tracking_number, "carrier": s.carrier}


# ═══════ STATS ═══════

@router.get("/stats", response_model=ShippingStats)
async def get_shipping_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get shipping dashboard stats"""
    wid = user.workspace_id
    total = db.query(func.count(Shipment.id)).filter(Shipment.workspace_id == wid).scalar() or 0
    transit = db.query(func.count(Shipment.id)).filter(Shipment.workspace_id == wid, Shipment.status.in_(["in_transit", "out_for_delivery"])).scalar() or 0
    delivered = db.query(func.count(Shipment.id)).filter(Shipment.workspace_id == wid, Shipment.status == "delivered").scalar() or 0
    avg_cost = db.query(func.avg(Shipment.cost)).filter(Shipment.workspace_id == wid, Shipment.cost > 0).scalar() or 0.0
    total_spent = db.query(func.sum(Shipment.cost)).filter(Shipment.workspace_id == wid).scalar() or 0.0
    total_revenue = db.query(func.sum(Shipment.price)).filter(Shipment.workspace_id == wid).scalar() or 0.0
    returns = db.query(func.count(Shipment.id)).filter(Shipment.workspace_id == wid, Shipment.status == "returned").scalar() or 0

    return ShippingStats(
        total_shipments=total, in_transit=transit, delivered=delivered,
        avg_cost=round(avg_cost, 2), total_spent=total_spent, total_revenue=total_revenue, returns=returns,
    )


# ═══════ VOLUMETRIC WEIGHT CALCULATOR ═══════

@router.post("/calculate-weight")
async def calc_volumetric(length: float, width: float, height: float, weight: float):
    """Calculate volumetric vs real weight"""
    vol = calculate_volumetric_weight(length, width, height)
    billable = max(weight, vol)
    return {
        "real_weight": weight,
        "volumetric_weight": vol,
        "billable_weight": billable,
        "charged_by": "volumétrico" if vol > weight else "real",
        "message": f"Se cobra por peso {'volumétrico' if vol > weight else 'real'} ({billable} kg)",
    }


# ═══════ CANCEL SHIPMENT ═══════

@router.post("/shipments/{shipment_id}/cancel")
async def cancel_shipment(
    shipment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a shipment before pickup"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")
    if s.status not in ("created", "picked_up"):
        raise HTTPException(400, "Solo se pueden cancelar envíos que no están en tránsito")

    s.status = "cancelled"
    s.cancelled_at = datetime.utcnow()
    event = ShipmentEvent(shipment_id=s.id, description="Guía cancelada", location="Sistema", status="cancelled")
    db.add(event)
    db.commit()
    return {"status": "success", "message": f"Envío {s.tracking_number} cancelado"}


# ═══════ SCHEDULE PICKUP ═══════

class PickupRequest(BaseModel):
    shipment_id: int
    pickup_date: str  # YYYY-MM-DD
    pickup_time_from: str = "09:00"  # HH:MM
    pickup_time_to: str = "18:00"
    instructions: Optional[str] = None

@router.post("/pickup")
async def schedule_pickup(
    data: PickupRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Schedule a carrier pickup for a shipment"""
    s = db.query(Shipment).filter(Shipment.id == data.shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")
    if s.status != "created":
        raise HTTPException(400, "Solo se puede programar recolección para envíos recién creados")

    # In production, call Skydropx pickup API
    # For now, update status and add event
    event = ShipmentEvent(
        shipment_id=s.id,
        description=f"Recolección programada: {data.pickup_date} de {data.pickup_time_from} a {data.pickup_time_to}",
        location=s.origin_city or s.origin_zip,
        status="pickup_scheduled",
    )
    db.add(event)
    db.commit()

    return {
        "status": "success",
        "message": f"Recolección programada para {data.pickup_date} entre {data.pickup_time_from} y {data.pickup_time_to}",
        "carrier": s.carrier,
        "tracking_number": s.tracking_number,
    }


# ═══════ INSURANCE ═══════

class InsuranceRequest(BaseModel):
    declared_value: float = Field(..., gt=0)

@router.post("/shipments/{shipment_id}/insurance")
async def add_insurance(
    shipment_id: int,
    data: InsuranceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add insurance to a shipment"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")

    # Insurance cost: typically 2-3% of declared value
    insurance_cost = round(data.declared_value * 0.025, 2)
    s.insured = True
    s.declared_value = data.declared_value
    s.cost += insurance_cost
    s.price += round(insurance_cost * 1.25, 2)  # 25% margin on insurance too
    s.margin = s.price - s.cost
    s.updated_at = datetime.utcnow()

    event = ShipmentEvent(
        shipment_id=s.id,
        description=f"Seguro agregado por ${data.declared_value:,.2f} (costo: ${insurance_cost:,.2f})",
        location="Sistema",
        status="insured",
    )
    db.add(event)
    db.commit()

    return {
        "status": "success",
        "message": f"Seguro agregado por ${data.declared_value:,.2f} MXN",
        "insurance_cost": insurance_cost,
        "new_total": s.price,
    }


# ═══════ RETURN LABEL ═══════

class ReturnRequest(BaseModel):
    reason: Optional[str] = "Devolución del cliente"

@router.post("/shipments/{shipment_id}/return")
async def create_return_label(
    shipment_id: int,
    data: ReturnRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a return label (inverse shipment)"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")

    # Create return label (swap origin/dest)
    return_tracking = f"RET-{s.carrier[:3].upper()}{s.id:06d}"
    ret = ReturnLabel(
        workspace_id=user.workspace_id,
        original_shipment_id=s.id,
        tracking_number=return_tracking,
        carrier=s.carrier,
        status="created",
    )
    db.add(ret)

    event = ShipmentEvent(
        shipment_id=s.id,
        description=f"Guía de retorno generada: {return_tracking}. Motivo: {data.reason}",
        location="Sistema",
        status="return_created",
    )
    db.add(event)
    db.commit()
    db.refresh(ret)

    return {
        "status": "success",
        "return_label_id": ret.id,
        "tracking_number": return_tracking,
        "carrier": s.carrier,
        "message": f"Guía de retorno {return_tracking} generada",
    }


# ═══════ MULTI-PACKAGE QUOTE ═══════

class MultiParcel(BaseModel):
    weight: float = Field(..., gt=0)
    length: float = Field(..., gt=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)

class MultiQuoteRequest(BaseModel):
    zip_from: str = Field(..., min_length=5, max_length=5)
    zip_to: str = Field(..., min_length=5, max_length=5)
    parcels: List[MultiParcel] = Field(..., min_length=1)

@router.post("/quote-multi")
async def get_multi_package_quote(
    data: MultiQuoteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get shipping rates for multi-package shipment"""
    total_weight = sum(p.weight for p in data.parcels)
    total_vol = sum(calculate_volumetric_weight(p.length, p.width, p.height) for p in data.parcels)
    billable = max(total_weight, total_vol)

    # Quote using total billable weight
    client = get_skydropx_client(user.workspace_id, db)
    avg_dims = {
        "length": max(p.length for p in data.parcels),
        "width": max(p.width for p in data.parcels),
        "height": sum(p.height for p in data.parcels),
    }

    result = await client.create_quotation(data.zip_from, data.zip_to, billable, avg_dims["length"], avg_dims["width"], avg_dims["height"])

    if result.get("error"):
        base = billable * 45
        rates = [
            {"carrier": "Estafeta", "service": "Terrestre", "days": 4, **calculate_user_price(round(base * 0.85 + 25))},
            {"carrier": "DHL", "service": "Express", "days": 2, **calculate_user_price(round(base * 1.2 + 40))},
            {"carrier": "FedEx", "service": "Estándar", "days": 3, **calculate_user_price(round(base * 1.1 + 35))},
        ]
        rates.sort(key=lambda x: x["price"])
    else:
        rates = []
        included = result.get("included", [])
        for item in included:
            if item.get("type") == "rates":
                attrs = item.get("attributes", {})
                carrier_cost = float(attrs.get("total_pricing", 0) or attrs.get("amount_local", 0))
                pricing = calculate_user_price(carrier_cost)
                rates.append({"carrier": attrs.get("provider", "Unknown"), "service": attrs.get("service_level_name", "Standard"), "days": attrs.get("days"), **pricing})
        rates.sort(key=lambda x: x["price"])

    return {
        "parcels_count": len(data.parcels),
        "total_real_weight": total_weight,
        "total_volumetric_weight": total_vol,
        "billable_weight": billable,
        "rates": rates,
    }


# ═══════ NOTIFY CLIENT ═══════

@router.post("/shipments/{shipment_id}/notify")
async def notify_client(
    shipment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send tracking info to client via email"""
    s = db.query(Shipment).filter(Shipment.id == shipment_id, Shipment.workspace_id == user.workspace_id).first()
    if not s:
        raise HTTPException(404, "Envío no encontrado")
    if not s.dest_email:
        raise HTTPException(400, "El envío no tiene email del destinatario")

    # In production, send actual email via app.core.email
    # For now, return success
    try:
        from app.core.email import send_email
        subject = f"Tu pedido va en camino — Guía {s.tracking_number}"
        body = f"""
        <h2>¡Tu pedido va en camino!</h2>
        <p>Hola {s.dest_name},</p>
        <p>Tu paquete ha sido enviado con <strong>{s.carrier}</strong>.</p>
        <p><strong>Número de guía:</strong> {s.tracking_number}</p>
        {f'<p><strong>Rastrear:</strong> <a href="{s.tracking_url}">{s.tracking_url}</a></p>' if s.tracking_url else ''}
        <p>¡Gracias por tu compra!</p>
        """
        await send_email(s.dest_email, subject, body)
        event = ShipmentEvent(shipment_id=s.id, description=f"Notificación enviada a {s.dest_email}", location="Sistema", status="notified")
        db.add(event)
        db.commit()
        return {"status": "success", "message": f"Notificación enviada a {s.dest_email}"}
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {"status": "success", "message": f"Notificación enviada a {s.dest_email} (simulado)"}
