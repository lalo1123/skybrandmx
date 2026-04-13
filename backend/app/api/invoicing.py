"""
Invoicing API — SkyBrandMX
CFDI 4.0 invoices, credit notes, fiscal clients, SAT catalog
"""
import re
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.core.deps import get_current_user, get_db
from app.models.base import User
from app.models.invoicing import Invoice, InvoiceItem, CreditNote, FiscalClient
from app.schemas.invoicing_schemas import (
    InvoiceCreate, InvoiceResponse, InvoiceCancelRequest,
    CreditNoteCreate, CreditNoteResponse,
    FiscalClientCreate, FiscalClientUpdate, FiscalClientResponse,
    InvoiceStats, RFCValidateRequest, RFCValidateResponse,
)
from app.integrations.facturapi_service import (
    get_facturapi_client, build_facturapi_invoice_payload
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════

@router.post("/invoices", response_model=InvoiceResponse)
async def create_invoice(
    data: InvoiceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create and stamp a CFDI 4.0 invoice"""
    wid = user.workspace_id

    # Generate folio
    last = db.query(func.max(Invoice.id)).filter(Invoice.workspace_id == wid).scalar() or 0
    folio = f"A-{str(last + 1).zfill(3)}"

    # Calculate totals from items
    subtotal = 0.0
    iva_total = 0.0
    discount_total = 0.0
    items_data = []

    for item in data.items:
        item_subtotal = item.quantity * item.unit_price
        item_discount = item.discount or 0
        item_iva = (item_subtotal - item_discount) * item.iva_rate
        item_total = item_subtotal - item_discount + item_iva

        subtotal += item_subtotal
        iva_total += item_iva
        discount_total += item_discount

        items_data.append({
            "description": item.description,
            "product_code": item.product_code,
            "unit_code": item.unit_code,
            "unit_name": item.unit_name or "Servicio",
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount": item_discount,
            "subtotal": round(item_subtotal, 2),
            "tax_object": item.tax_object,
            "iva_rate": item.iva_rate,
            "iva_amount": round(item_iva, 2),
            "isr_rate": item.isr_rate,
            "isr_amount": 0.0,
            "total": round(item_total, 2),
        })

    total = round(subtotal - discount_total + iva_total, 2)

    # Create invoice in DB
    invoice = Invoice(
        workspace_id=wid,
        folio=folio,
        cfdi_type=data.cfdi_type,
        receiver_name=data.receiver_name,
        receiver_rfc=data.receiver_rfc.upper(),
        receiver_regime=data.receiver_regime,
        receiver_zip=data.receiver_zip,
        receiver_email=data.receiver_email,
        receiver_cfdi_use=data.receiver_cfdi_use,
        fiscal_client_id=data.fiscal_client_id,
        payment_form=data.payment_form,
        payment_method=data.payment_method,
        currency=data.currency,
        exchange_rate=data.exchange_rate,
        subtotal=round(subtotal, 2),
        discount=round(discount_total, 2),
        iva_total=round(iva_total, 2),
        total=total,
        status="stamping",
        notes=data.notes,
        order_id=data.order_id,
        issuer_rfc=data.issuer_rfc,
        issuer_name=data.issuer_name,
        issuer_regime=data.issuer_regime,
        expedition_place=data.expedition_place,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Create items
    db_items = []
    for item_data in items_data:
        db_item = InvoiceItem(invoice_id=invoice.id, **item_data)
        db.add(db_item)
        db_items.append(db_item)
    db.commit()

    # Stamp with Facturapi
    try:
        client = get_facturapi_client(wid, db)
        invoice_dict = data.dict()
        invoice_dict["receiver_name"] = data.receiver_name
        invoice_dict["receiver_rfc"] = data.receiver_rfc.upper()
        invoice_dict["receiver_regime"] = data.receiver_regime
        invoice_dict["receiver_zip"] = data.receiver_zip
        invoice_dict["receiver_cfdi_use"] = data.receiver_cfdi_use
        invoice_dict["payment_form"] = data.payment_form
        invoice_dict["payment_method"] = data.payment_method
        invoice_dict["currency"] = data.currency
        invoice_dict["cfdi_type"] = data.cfdi_type

        payload = build_facturapi_invoice_payload(invoice_dict, items_data)
        result = await client.create_invoice(payload)

        if result.get("error"):
            invoice.status = "error"
            invoice.error_message = str(result.get("detail", {}).get("message", "Error al timbrar"))
            db.commit()
            logger.error(f"Facturapi stamp error for invoice {folio}: {invoice.error_message}")
        else:
            invoice.status = "stamped"
            invoice.facturapi_id = result.get("id")
            invoice.uuid = result.get("uuid")
            invoice.stamp_date = datetime.utcnow()
            # Build download URLs
            if invoice.facturapi_id:
                invoice.pdf_url = f"/api/v1/invoicing/invoices/{invoice.id}/pdf"
                invoice.xml_url = f"/api/v1/invoicing/invoices/{invoice.id}/xml"
            db.commit()

            # Update fiscal client counter
            if data.fiscal_client_id:
                fc = db.query(FiscalClient).filter(FiscalClient.id == data.fiscal_client_id).first()
                if fc:
                    fc.invoice_count += 1
                    fc.total_invoiced += total
                    db.commit()

            # Send email if requested
            if data.send_email and data.receiver_email and invoice.facturapi_id:
                try:
                    await client.send_by_email(invoice.facturapi_id, data.receiver_email)
                except Exception as e:
                    logger.error(f"Error sending invoice email: {e}")

            logger.info(f"Invoice {folio} stamped: UUID={invoice.uuid}")

    except Exception as e:
        invoice.status = "error"
        invoice.error_message = f"Error de conexión: {str(e)}"
        db.commit()
        logger.error(f"Exception stamping invoice {folio}: {e}")

    # Refresh to get items
    db.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List invoices with filters"""
    q = db.query(Invoice).filter(Invoice.workspace_id == user.workspace_id)

    if search:
        search_term = f"%{search}%"
        q = q.filter(
            (Invoice.folio.ilike(search_term)) |
            (Invoice.receiver_name.ilike(search_term)) |
            (Invoice.receiver_rfc.ilike(search_term))
        )

    if status:
        q = q.filter(Invoice.status == status)

    invoices = q.order_by(Invoice.created_at.desc()).offset(offset).limit(limit).all()
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get invoice details"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada")
    return invoice


@router.post("/invoices/{invoice_id}/cancel")
async def cancel_invoice(
    invoice_id: int,
    data: InvoiceCancelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel invoice with SAT"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada")
    if invoice.status != "stamped":
        raise HTTPException(400, "Solo se pueden cancelar facturas timbradas")

    if invoice.facturapi_id:
        client = get_facturapi_client(user.workspace_id, db)
        result = await client.cancel_invoice(invoice.facturapi_id, data.reason, data.substitute_uuid)
        if result.get("error"):
            raise HTTPException(400, f"Error al cancelar: {result.get('detail', {}).get('message', 'Error')}")

    invoice.status = "cancelled"
    invoice.cancellation_reason = data.reason
    invoice.substitute_uuid = data.substitute_uuid
    invoice.cancelled_at = datetime.utcnow()
    db.commit()

    return {"status": "success", "message": f"Factura {invoice.folio} cancelada"}


@router.get("/invoices/{invoice_id}/pdf")
async def download_pdf(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download invoice PDF"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice or not invoice.facturapi_id:
        raise HTTPException(404, "Factura no encontrada o no timbrada")

    client = get_facturapi_client(user.workspace_id, db)
    pdf_data = await client.download_pdf(invoice.facturapi_id)

    if isinstance(pdf_data, dict) and pdf_data.get("error"):
        raise HTTPException(400, "Error al descargar PDF")

    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={invoice.folio}.pdf"}
    )


@router.get("/invoices/{invoice_id}/xml")
async def download_xml(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download invoice XML"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice or not invoice.facturapi_id:
        raise HTTPException(404, "Factura no encontrada o no timbrada")

    client = get_facturapi_client(user.workspace_id, db)
    xml_data = await client.download_xml(invoice.facturapi_id)

    if isinstance(xml_data, dict) and xml_data.get("error"):
        raise HTTPException(400, "Error al descargar XML")

    return Response(
        content=xml_data,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={invoice.folio}.xml"}
    )


@router.post("/invoices/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send invoice by email"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada")
    if not invoice.receiver_email:
        raise HTTPException(400, "La factura no tiene email del receptor")
    if not invoice.facturapi_id:
        raise HTTPException(400, "La factura no ha sido timbrada")

    client = get_facturapi_client(user.workspace_id, db)
    result = await client.send_by_email(invoice.facturapi_id, invoice.receiver_email)

    if result.get("error"):
        raise HTTPException(400, "Error al enviar email")

    return {"status": "success", "message": f"Factura enviada a {invoice.receiver_email}"}


@router.post("/invoices/{invoice_id}/credit-note", response_model=CreditNoteResponse)
async def create_credit_note(
    invoice_id: int,
    data: CreditNoteCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create credit note for an invoice"""
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.workspace_id == user.workspace_id
    ).first()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada")

    last_cn = db.query(func.max(CreditNote.id)).filter(CreditNote.workspace_id == user.workspace_id).scalar() or 0
    cn_folio = f"NC-{str(last_cn + 1).zfill(3)}"

    cn = CreditNote(
        workspace_id=user.workspace_id,
        original_invoice_id=invoice.id,
        original_folio=invoice.folio,
        folio=cn_folio,
        amount=data.amount,
        reason=data.reason,
        status="stamped",
    )
    db.add(cn)
    db.commit()
    db.refresh(cn)

    return cn


# ═══════════════════════════════════════
# FISCAL CLIENTS
# ═══════════════════════════════════════

@router.get("/clients", response_model=list[FiscalClientResponse])
async def list_fiscal_clients(
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List fiscal clients"""
    q = db.query(FiscalClient).filter(FiscalClient.workspace_id == user.workspace_id)
    if search:
        q = q.filter(
            (FiscalClient.name.ilike(f"%{search}%")) |
            (FiscalClient.rfc.ilike(f"%{search}%"))
        )
    return q.order_by(FiscalClient.name).all()


@router.post("/clients", response_model=FiscalClientResponse)
async def create_fiscal_client(
    data: FiscalClientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create fiscal client"""
    client = FiscalClient(
        workspace_id=user.workspace_id,
        **data.dict(),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.put("/clients/{client_id}", response_model=FiscalClientResponse)
async def update_fiscal_client(
    client_id: int,
    data: FiscalClientUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update fiscal client"""
    client = db.query(FiscalClient).filter(
        FiscalClient.id == client_id,
        FiscalClient.workspace_id == user.workspace_id,
    ).first()
    if not client:
        raise HTTPException(404, "Cliente fiscal no encontrado")

    for key, val in data.dict(exclude_unset=True).items():
        setattr(client, key, val)
    client.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client


@router.delete("/clients/{client_id}")
async def delete_fiscal_client(
    client_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete fiscal client"""
    client = db.query(FiscalClient).filter(
        FiscalClient.id == client_id,
        FiscalClient.workspace_id == user.workspace_id,
    ).first()
    if not client:
        raise HTTPException(404, "Cliente fiscal no encontrado")
    db.delete(client)
    db.commit()
    return {"status": "success", "message": "Cliente eliminado"}


# ═══════════════════════════════════════
# STATS
# ═══════════════════════════════════════

@router.get("/stats", response_model=InvoiceStats)
async def get_invoice_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get invoicing dashboard stats"""
    wid = user.workspace_id
    now = datetime.utcnow()

    total = db.query(func.count(Invoice.id)).filter(
        Invoice.workspace_id == wid,
        Invoice.status != "error",
    ).scalar() or 0

    total_amount = db.query(func.sum(Invoice.total)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
    ).scalar() or 0.0

    pending = db.query(func.sum(Invoice.total)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
        Invoice.payment_method == "PPD",
    ).scalar() or 0.0

    cn_count = db.query(func.count(CreditNote.id)).filter(
        CreditNote.workspace_id == wid
    ).scalar() or 0

    iva = db.query(func.sum(Invoice.iva_total)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
        extract('month', Invoice.created_at) == now.month,
        extract('year', Invoice.created_at) == now.year,
    ).scalar() or 0.0

    today = db.query(func.count(Invoice.id)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
        func.date(Invoice.stamp_date) == now.date(),
    ).scalar() or 0

    month_inv = db.query(func.count(Invoice.id)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
        extract('month', Invoice.created_at) == now.month,
        extract('year', Invoice.created_at) == now.year,
    ).scalar() or 0

    month_amount = db.query(func.sum(Invoice.total)).filter(
        Invoice.workspace_id == wid,
        Invoice.status == "stamped",
        extract('month', Invoice.created_at) == now.month,
        extract('year', Invoice.created_at) == now.year,
    ).scalar() or 0.0

    return InvoiceStats(
        total_invoices=total,
        total_amount=total_amount,
        pending_amount=pending,
        credit_notes_count=cn_count,
        iva_total=iva,
        stamped_today=today,
        month_invoices=month_inv,
        month_amount=month_amount,
    )


# ═══════════════════════════════════════
# RFC VALIDATION
# ═══════════════════════════════════════

@router.post("/validate-rfc", response_model=RFCValidateResponse)
async def validate_rfc(data: RFCValidateRequest):
    """Validate RFC format"""
    rfc = data.rfc.upper().strip()

    if rfc in ('XAXX010101000', 'XEXX010101000'):
        return RFCValidateResponse(
            rfc=rfc,
            valid=True,
            type="generico",
            message="RFC genérico válido (público en general o extranjero)"
        )

    is_pf = bool(re.match(r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$', rfc))
    is_pm = bool(re.match(r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$', rfc))

    if is_pf:
        return RFCValidateResponse(rfc=rfc, valid=True, type="persona_fisica", message="RFC válido — Persona Física (13 caracteres)")
    elif is_pm:
        return RFCValidateResponse(rfc=rfc, valid=True, type="persona_moral", message="RFC válido — Persona Moral (12 caracteres)")
    else:
        return RFCValidateResponse(rfc=rfc, valid=False, type="desconocido", message="RFC inválido. Verifica que tenga 12 o 13 caracteres.")


# ═══════════════════════════════════════
# SAT CATALOGS
# ═══════════════════════════════════════

SAT_REGIMES = [
    {"code": "601", "name": "General de Ley Personas Morales"},
    {"code": "603", "name": "Personas Morales con Fines no Lucrativos"},
    {"code": "605", "name": "Sueldos y Salarios e Ingresos Asimilados a Salarios"},
    {"code": "606", "name": "Arrendamiento"},
    {"code": "607", "name": "Régimen de Enajenación o Adquisición de Bienes"},
    {"code": "608", "name": "Demás ingresos"},
    {"code": "610", "name": "Residentes en el Extranjero sin Establecimiento Permanente"},
    {"code": "611", "name": "Ingresos por Dividendos"},
    {"code": "612", "name": "Personas Físicas con Actividades Empresariales y Profesionales"},
    {"code": "614", "name": "Ingresos por intereses"},
    {"code": "616", "name": "Sin obligaciones fiscales"},
    {"code": "620", "name": "Sociedades Cooperativas de Producción"},
    {"code": "621", "name": "Incorporación Fiscal"},
    {"code": "622", "name": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras"},
    {"code": "623", "name": "Opcional para Grupos de Sociedades"},
    {"code": "624", "name": "Coordinados"},
    {"code": "625", "name": "Régimen de las Actividades Empresariales con ingresos por Plataformas Tecnológicas"},
    {"code": "626", "name": "Régimen Simplificado de Confianza"},
]

SAT_CFDI_USES = [
    {"code": "G01", "name": "Adquisición de mercancías"},
    {"code": "G02", "name": "Devoluciones, descuentos o bonificaciones"},
    {"code": "G03", "name": "Gastos en general"},
    {"code": "I01", "name": "Construcciones"},
    {"code": "I02", "name": "Mobiliario y equipo de oficina"},
    {"code": "I03", "name": "Equipo de transporte"},
    {"code": "I04", "name": "Equipo de cómputo y accesorios"},
    {"code": "I08", "name": "Otra maquinaria y equipo"},
    {"code": "D01", "name": "Honorarios médicos, dentales y gastos hospitalarios"},
    {"code": "D02", "name": "Gastos médicos por incapacidad o discapacidad"},
    {"code": "D03", "name": "Gastos funerales"},
    {"code": "D04", "name": "Donativos"},
    {"code": "D10", "name": "Pagos por servicios educativos"},
    {"code": "P01", "name": "Por definir"},
    {"code": "S01", "name": "Sin efectos fiscales"},
    {"code": "CP01", "name": "Pagos"},
]

SAT_PAYMENT_FORMS = [
    {"code": "01", "name": "Efectivo"},
    {"code": "02", "name": "Cheque nominativo"},
    {"code": "03", "name": "Transferencia electrónica de fondos"},
    {"code": "04", "name": "Tarjeta de crédito"},
    {"code": "06", "name": "Dinero electrónico"},
    {"code": "08", "name": "Vales de despensa"},
    {"code": "28", "name": "Tarjeta de débito"},
    {"code": "29", "name": "Tarjeta de servicios"},
    {"code": "99", "name": "Por definir"},
]

@router.get("/catalog/regimes")
async def get_sat_regimes():
    return SAT_REGIMES

@router.get("/catalog/cfdi-uses")
async def get_sat_cfdi_uses():
    return SAT_CFDI_USES

@router.get("/catalog/payment-forms")
async def get_sat_payment_forms():
    return SAT_PAYMENT_FORMS
