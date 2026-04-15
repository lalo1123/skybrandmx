"""Product and Category database models."""
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Product(SQLModel, table=True):
    __tablename__ = "product"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")

    # Identity
    name: str = Field(max_length=255)
    sku: Optional[str] = Field(default=None, max_length=50, index=True)
    barcode: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None

    # Pricing
    price: float = Field(default=0.0)
    compare_at_price: Optional[float] = None  # "compare" in frontend
    cost: float = Field(default=0.0)

    # Inventory
    stock: int = Field(default=0)
    low_stock_threshold: int = Field(default=5)
    track_inventory: bool = Field(default=True)

    # Physical
    weight: Optional[float] = None  # kg

    # Organization
    category: Optional[str] = None
    tags: Optional[str] = None  # JSON array

    # Media
    images: Optional[str] = None  # JSON array of URLs

    # Status: activo, agotado, borrador
    status: str = Field(default="activo", max_length=20)

    # Variants
    sizes: Optional[str] = None  # comma-separated: "CH, M, G, XG"
    colors: Optional[str] = None  # comma-separated: "Rojo, Azul"

    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    # Stats
    sold: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True, foreign_key="workspace.id")
    name: str = Field(max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = Field(default=None, max_length=10)
    product_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
