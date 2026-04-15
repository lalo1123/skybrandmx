"""
Shipping models — SkyBrandMX
Supports: Quotations, Shipments, Labels, Tracking
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class Shipment(SQLModel, table=True):
    """Envío / Guía de paquetería"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)

    # Tracking
    tracking_number: Optional[str] = Field(default=None, max_length=50, index=True)
    carrier: str = Field(max_length=50)  # DHL, Estafeta, FedEx, Redpack, 99Minutos, etc.
    service_level: Optional[str] = Field(default=None, max_length=100)  # Express, Terrestre, etc.

    # Status
    status: str = Field(default="created", max_length=20)  # created, picked_up, in_transit, out_for_delivery, delivered, returned, cancelled
    estimated_days: Optional[int] = Field(default=None)

    # Addresses
    origin_name: Optional[str] = Field(default=None, max_length=200)
    origin_zip: str = Field(max_length=5)
    origin_city: Optional[str] = Field(default=None, max_length=100)
    origin_state: Optional[str] = Field(default=None, max_length=100)
    origin_street: Optional[str] = Field(default=None, max_length=300)
    origin_phone: Optional[str] = Field(default=None, max_length=20)

    dest_name: str = Field(max_length=200)
    dest_zip: str = Field(max_length=5)
    dest_city: Optional[str] = Field(default=None, max_length=100)
    dest_state: Optional[str] = Field(default=None, max_length=100)
    dest_street: Optional[str] = Field(default=None, max_length=300)
    dest_phone: Optional[str] = Field(default=None, max_length=20)
    dest_email: Optional[str] = Field(default=None, max_length=255)

    # Parcel
    weight: float = Field(default=1.0)  # kg
    length: float = Field(default=30.0)  # cm
    width: float = Field(default=20.0)  # cm
    height: float = Field(default=15.0)  # cm
    volumetric_weight: Optional[float] = Field(default=None)
    content_description: Optional[str] = Field(default=None, max_length=200)
    declared_value: float = Field(default=0.0)
    insured: bool = Field(default=False)

    # COD (contra entrega)
    cod_enabled: bool = Field(default=False)
    cod_amount: float = Field(default=0.0)
    cod_payment_method: Optional[str] = Field(default=None, max_length=20)  # cash, card, transfer

    # Carta Porte
    carta_porte: bool = Field(default=False)
    merchandise_description: Optional[str] = Field(default=None, max_length=300)
    sat_product_key: Optional[str] = Field(default=None, max_length=20)

    # Pickup
    pickup_scheduled: bool = Field(default=False)
    pickup_date: Optional[str] = Field(default=None, max_length=10)
    pickup_time_from: Optional[str] = Field(default=None, max_length=5)
    pickup_time_to: Optional[str] = Field(default=None, max_length=5)

    # Notifications
    notify_on_create: bool = Field(default=True)
    notify_on_transit: bool = Field(default=False)
    notify_on_delivery: bool = Field(default=True)

    # Costs
    cost: float = Field(default=0.0)  # What we pay Skydropx
    price: float = Field(default=0.0)  # What user pays (cost + margin)
    margin: float = Field(default=0.0)

    # Skydropx IDs
    skydropx_quotation_id: Optional[str] = Field(default=None, max_length=100)
    skydropx_rate_id: Optional[str] = Field(default=None, max_length=100)
    skydropx_shipment_id: Optional[str] = Field(default=None, max_length=100)
    skydropx_label_id: Optional[str] = Field(default=None, max_length=100)

    # URLs
    label_url: Optional[str] = Field(default=None, max_length=500)
    tracking_url: Optional[str] = Field(default=None, max_length=500)

    # Relations
    order_id: Optional[int] = Field(default=None)  # FK a pedido
    invoice_id: Optional[int] = Field(default=None)  # FK a factura

    # Timestamps
    picked_up_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    # Events
    events: List["ShipmentEvent"] = Relationship(back_populates="shipment")


class ShipmentEvent(SQLModel, table=True):
    """Evento de rastreo de un envío"""
    id: Optional[int] = Field(default=None, primary_key=True)
    shipment_id: int = Field(foreign_key="shipment.id", index=True)
    description: str = Field(max_length=300)
    location: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = Field(default=None, max_length=50)
    event_date: Optional[datetime] = Field(default_factory=datetime.utcnow)

    shipment: Optional[Shipment] = Relationship(back_populates="events")


class ReturnLabel(SQLModel, table=True):
    """Guía de retorno / devolución"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    original_shipment_id: int = Field(foreign_key="shipment.id")
    tracking_number: Optional[str] = Field(default=None, max_length=50)
    carrier: str = Field(max_length=50)
    status: str = Field(default="created", max_length=20)
    label_url: Optional[str] = Field(default=None, max_length=500)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class SavedAddress(SQLModel, table=True):
    """Dirección guardada — libreta de direcciones"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    label: str = Field(max_length=100)  # "Mi bodega", "Oficina CDMX"
    is_origin: bool = Field(default=True)  # True=origin, False=destination
    is_default: bool = Field(default=False)
    name: str = Field(max_length=200)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    street: Optional[str] = Field(default=None, max_length=300)
    ext_number: Optional[str] = Field(default=None, max_length=20)
    int_number: Optional[str] = Field(default=None, max_length=20)
    colony: Optional[str] = Field(default=None, max_length=200)
    zip_code: str = Field(max_length=5)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    municipality: Optional[str] = Field(default=None, max_length=100)
    reference: Optional[str] = Field(default=None, max_length=300)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
