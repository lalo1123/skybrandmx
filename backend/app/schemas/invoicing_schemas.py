"""
Pydantic schemas for Invoicing API — SkyBrandMX
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
import re


# ═══════ INVOICE ITEM ═══════
class InvoiceItemCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=1000)
    product_code: str = Field(default="01010101", max_length=8)
    unit_code: str = Field(default="E48", max_length=3)
    unit_name: Optional[str] = "Servicio"
    quantity: float = Field(default=1.0, gt=0)
    unit_price: float = Field(default=0.0, ge=0)
    discount: float = Field(default=0.0, ge=0)
    tax_object: str = Field(default="02")
    iva_rate: float = Field(default=0.16, ge=0, le=1)
    isr_rate: float = Field(default=0.0, ge=0, le=1)


class InvoiceItemResponse(BaseModel):
    id: int
    description: str
    product_code: str
    unit_code: str
    quantity: float
    unit_price: float
    discount: float
    subtotal: float
    iva_rate: float
    iva_amount: float
    total: float

    class Config:
        from_attributes = True


# ═══════ INVOICE ═══════
class InvoiceCreate(BaseModel):
    # Receptor
    receiver_name: str = Field(..., min_length=1, max_length=300)
    receiver_rfc: str = Field(..., min_length=12, max_length=13)
    receiver_regime: str = Field(..., min_length=3, max_length=3)
    receiver_zip: str = Field(..., min_length=5, max_length=5)
    receiver_email: Optional[str] = None
    receiver_cfdi_use: str = Field(default="G03", max_length=4)
    fiscal_client_id: Optional[int] = None

    # Payment
    payment_form: str = Field(default="03", max_length=2)
    payment_method: str = Field(default="PUE", max_length=3)
    currency: str = Field(default="MXN", max_length=3)
    exchange_rate: float = Field(default=1.0)

    # Items
    items: List[InvoiceItemCreate] = Field(..., min_length=1)

    # Optional
    cfdi_type: str = Field(default="I", max_length=1)
    notes: Optional[str] = None
    order_id: Optional[int] = None
    send_email: bool = Field(default=True)  # Auto-send to receiver

    # Issuer override (multiemisor)
    issuer_rfc: Optional[str] = None
    issuer_name: Optional[str] = None
    issuer_regime: Optional[str] = None
    expedition_place: Optional[str] = None

    @validator('receiver_rfc')
    def validate_rfc(cls, v):
        v = v.upper().strip()
        # Persona física (13 chars) or moral (12 chars) or genérico
        if v in ('XAXX010101000', 'XEXX010101000'):
            return v
        if not re.match(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$', v):
            raise ValueError('RFC inválido. Debe tener 12 (moral) o 13 (física) caracteres.')
        return v

    @validator('receiver_zip')
    def validate_zip(cls, v):
        if not re.match(r'^\d{5}$', v):
            raise ValueError('Código postal debe ser de 5 dígitos')
        return v


class InvoiceResponse(BaseModel):
    id: int
    workspace_id: int
    folio: str
    serie: str
    cfdi_type: str
    receiver_name: str
    receiver_rfc: str
    receiver_regime: str
    receiver_zip: str
    receiver_email: Optional[str]
    receiver_cfdi_use: str
    payment_form: str
    payment_method: str
    currency: str
    subtotal: float
    discount: float
    iva_total: float
    total: float
    status: str
    error_message: Optional[str]
    facturapi_id: Optional[str]
    uuid: Optional[str]
    xml_url: Optional[str]
    pdf_url: Optional[str]
    stamp_date: Optional[datetime]
    cancellation_reason: Optional[str]
    cancelled_at: Optional[datetime]
    notes: Optional[str]
    items: List[InvoiceItemResponse] = []
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class InvoiceCancelRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=2)  # 01, 02, 03, 04
    substitute_uuid: Optional[str] = None  # Required for reason 01

    @validator('reason')
    def validate_reason(cls, v):
        valid = {'01': 'CFDI emitido con errores con relación',
                 '02': 'CFDI emitido con errores sin relación',
                 '03': 'No se llevó a cabo la operación',
                 '04': 'Operación nominativa relacionada en CFDI global'}
        if v not in valid:
            raise ValueError(f'Motivo inválido. Opciones: {list(valid.keys())}')
        return v


# ═══════ CREDIT NOTE ═══════
class CreditNoteCreate(BaseModel):
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)


class CreditNoteResponse(BaseModel):
    id: int
    original_invoice_id: int
    original_folio: str
    folio: str
    amount: float
    reason: str
    facturapi_id: Optional[str]
    uuid: Optional[str]
    status: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════ FISCAL CLIENT ═══════
class FiscalClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    rfc: str = Field(..., min_length=12, max_length=13)
    fiscal_regime: str = Field(..., min_length=3, max_length=3)
    zip_code: str = Field(..., min_length=5, max_length=5)
    email: Optional[str] = None
    cfdi_use_default: str = Field(default="G03")
    address: Optional[str] = None
    phone: Optional[str] = None

    @validator('rfc')
    def validate_rfc(cls, v):
        return v.upper().strip()


class FiscalClientUpdate(BaseModel):
    name: Optional[str] = None
    rfc: Optional[str] = None
    fiscal_regime: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[str] = None
    cfdi_use_default: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None


class FiscalClientResponse(BaseModel):
    id: int
    name: str
    rfc: str
    fiscal_regime: str
    zip_code: str
    email: Optional[str]
    cfdi_use_default: str
    invoice_count: int
    total_invoiced: float
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════ STATS ═══════
class InvoiceStats(BaseModel):
    total_invoices: int = 0
    total_amount: float = 0.0
    pending_amount: float = 0.0  # facturas no pagadas
    credit_notes_count: int = 0
    iva_total: float = 0.0
    stamped_today: int = 0
    month_invoices: int = 0
    month_amount: float = 0.0


# ═══════ RFC VALIDATION ═══════
class RFCValidateRequest(BaseModel):
    rfc: str = Field(..., min_length=12, max_length=13)


class RFCValidateResponse(BaseModel):
    rfc: str
    valid: bool
    type: str  # "persona_fisica", "persona_moral", "generico"
    message: str
