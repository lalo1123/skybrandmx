"""
Invoicing models for CFDI 4.0 — SkyBrandMX
Supports: Facturas, Notas de Crédito, Complementos de Pago, Clientes Fiscales
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, JSON


class FiscalClient(SQLModel, table=True):
    """Cliente fiscal — datos para facturar"""

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    name: str = Field(max_length=300)  # Razón social
    rfc: str = Field(max_length=13, index=True)  # RFC
    fiscal_regime: str = Field(max_length=3)  # Código régimen SAT (601, 612, 626, etc.)
    zip_code: str = Field(max_length=5)  # Código postal fiscal
    email: Optional[str] = Field(default=None, max_length=255)
    cfdi_use_default: str = Field(default="G03", max_length=4)  # Uso CFDI por default
    address: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=20)
    facturapi_customer_id: Optional[str] = Field(default=None, max_length=100)  # ID en Facturapi
    invoice_count: int = Field(default=0)
    total_invoiced: float = Field(default=0.0)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Invoice(SQLModel, table=True):
    """Factura CFDI 4.0"""

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    folio: str = Field(max_length=20, index=True)  # A-001, A-002, etc.
    serie: str = Field(default="A", max_length=10)

    # Tipo de CFDI
    cfdi_type: str = Field(default="I", max_length=1)  # I=Ingreso, E=Egreso, P=Pago

    # Receptor
    receiver_name: str = Field(max_length=300)
    receiver_rfc: str = Field(max_length=13)
    receiver_regime: str = Field(max_length=3)
    receiver_zip: str = Field(max_length=5)
    receiver_email: Optional[str] = Field(default=None, max_length=255)
    receiver_cfdi_use: str = Field(default="G03", max_length=4)
    fiscal_client_id: Optional[int] = Field(default=None, foreign_key="fiscalclient.id")

    # Pago
    payment_form: str = Field(default="03", max_length=2)  # 01=Efectivo, 03=Transferencia, 04=Tarjeta
    payment_method: str = Field(default="PUE", max_length=3)  # PUE o PPD
    currency: str = Field(default="MXN", max_length=3)
    exchange_rate: float = Field(default=1.0)

    # Montos
    subtotal: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    iva_total: float = Field(default=0.0)
    isr_retention: float = Field(default=0.0)
    total: float = Field(default=0.0)

    # Estado
    status: str = Field(default="draft", max_length=20)  # draft, stamping, stamped, cancelled, error
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Facturapi
    facturapi_id: Optional[str] = Field(default=None, max_length=100, index=True)
    uuid: Optional[str] = Field(default=None, max_length=36)  # UUID fiscal del SAT
    xml_url: Optional[str] = Field(default=None, max_length=500)
    pdf_url: Optional[str] = Field(default=None, max_length=500)
    stamp_date: Optional[datetime] = Field(default=None)

    # Cancelación
    cancellation_reason: Optional[str] = Field(default=None, max_length=2)  # 01, 02, 03, 04
    substitute_uuid: Optional[str] = Field(default=None, max_length=36)
    cancelled_at: Optional[datetime] = Field(default=None)

    # Relaciones opcionales
    order_id: Optional[int] = Field(default=None)  # FK a pedidos cuando exista
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Emisor info (para multiemisor)
    issuer_rfc: Optional[str] = Field(default=None, max_length=13)
    issuer_name: Optional[str] = Field(default=None, max_length=300)
    issuer_regime: Optional[str] = Field(default=None, max_length=3)
    expedition_place: Optional[str] = Field(default=None, max_length=5)

    # Timestamps
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # Relationship
    items: List["InvoiceItem"] = Relationship(back_populates="invoice")


class InvoiceItem(SQLModel, table=True):
    """Concepto/línea de factura"""

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoice.id", index=True)

    description: str = Field(max_length=1000)
    product_code: str = Field(default="01010101", max_length=8)  # Clave producto SAT
    unit_code: str = Field(default="E48", max_length=3)  # Clave unidad SAT
    unit_name: Optional[str] = Field(default="Servicio", max_length=50)

    quantity: float = Field(default=1.0)
    unit_price: float = Field(default=0.0)
    discount: float = Field(default=0.0)
    subtotal: float = Field(default=0.0)

    # Impuestos
    tax_object: str = Field(default="02", max_length=2)  # 01=No objeto, 02=Sí objeto, 03=Sí objeto no obligado
    iva_rate: float = Field(default=0.16)
    iva_amount: float = Field(default=0.0)
    isr_rate: float = Field(default=0.0)
    isr_amount: float = Field(default=0.0)

    total: float = Field(default=0.0)

    # Relationship
    invoice: Optional[Invoice] = Relationship(back_populates="items")


class CreditNote(SQLModel, table=True):
    """Nota de crédito"""

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    original_invoice_id: int = Field(foreign_key="invoice.id")
    original_folio: str = Field(max_length=20)

    folio: str = Field(max_length=20)
    amount: float = Field(default=0.0)
    reason: str = Field(max_length=500)

    facturapi_id: Optional[str] = Field(default=None, max_length=100)
    uuid: Optional[str] = Field(default=None, max_length=36)
    status: str = Field(default="stamped", max_length=20)  # stamped, cancelled

    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
