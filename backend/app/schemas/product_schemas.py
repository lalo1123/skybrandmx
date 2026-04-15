"""Pydantic schemas for Products API."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    price: float = 0.0
    compare_at_price: Optional[float] = None
    cost: float = 0.0
    stock: int = 0
    low_stock_threshold: int = 5
    weight: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[str]] = None
    status: str = "activo"
    sizes: Optional[str] = None
    colors: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    cost: Optional[float] = None
    stock: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    weight: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[str]] = None
    status: Optional[str] = None
    sizes: Optional[str] = None
    colors: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    sku: Optional[str]
    barcode: Optional[str]
    description: Optional[str]
    price: float
    compare_at_price: Optional[float]
    cost: float
    stock: int
    low_stock_threshold: int
    weight: Optional[float]
    category: Optional[str]
    tags: Optional[str]
    images: Optional[str]
    status: str
    sizes: Optional[str]
    colors: Optional[str]
    meta_title: Optional[str]
    meta_description: Optional[str]
    sold: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    product_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProductStats(BaseModel):
    total_products: int
    inventory_value: float
    out_of_stock: int
    low_stock: int
    categories_count: int
    avg_margin: float
