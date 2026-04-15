"""Products API endpoints — products CRUD, categories, stats."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.base import User
from ..models.product import Product, Category
from ..schemas.product_schemas import (
    ProductCreate, ProductUpdate, ProductResponse,
    CategoryCreate, CategoryResponse, ProductStats,
)

router = APIRouter()


# ===== STATS =====

@router.get("/stats", response_model=ProductStats)
def get_product_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get product dashboard stats."""
    ws = current_user.workspace_id

    total = db.query(Product).filter(
        Product.workspace_id == ws,
        Product.status != "archivado",
    ).count()

    inventory_value = db.query(func.sum(Product.cost * Product.stock)).filter(
        Product.workspace_id == ws,
        Product.status != "archivado",
    ).scalar() or 0.0

    out_of_stock = db.query(Product).filter(
        Product.workspace_id == ws,
        Product.stock == 0,
        Product.track_inventory == True,
        Product.status != "archivado",
    ).count()

    low_stock = db.query(Product).filter(
        Product.workspace_id == ws,
        Product.stock > 0,
        Product.stock <= Product.low_stock_threshold,
        Product.track_inventory == True,
        Product.status != "archivado",
    ).count()

    categories_count = db.query(Category).filter(
        Category.workspace_id == ws,
    ).count()

    # Average margin: avg((price - cost) / price * 100) for products where price > 0
    margins = db.query(
        func.avg((Product.price - Product.cost) / Product.price * 100)
    ).filter(
        Product.workspace_id == ws,
        Product.price > 0,
        Product.status != "archivado",
    ).scalar() or 0.0

    return ProductStats(
        total_products=total,
        inventory_value=round(inventory_value, 2),
        out_of_stock=out_of_stock,
        low_stock=low_stock,
        categories_count=categories_count,
        avg_margin=round(margins, 2),
    )


# ===== LIST / SEARCH =====

@router.get("/products", response_model=list[ProductResponse])
def list_products(
    search: str = Query(None, description="Search by name or SKU"),
    category: str = Query(None, description="Filter by category"),
    status: str = Query(None, description="Filter by status"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List products with search, filters, and pagination."""
    query = db.query(Product).filter(
        Product.workspace_id == current_user.workspace_id,
        Product.status != "archivado",
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            Product.name.ilike(search_term),
            Product.sku.ilike(search_term),
        ))

    if category:
        query = query.filter(Product.category == category)

    if status:
        query = query.filter(Product.status == status)

    # Sort
    sort_col = getattr(Product, sort, Product.created_at)
    if order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    products = query.offset(offset).limit(limit).all()
    return products


# ===== CRUD =====

@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single product."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.workspace_id == current_user.workspace_id,
    ).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    return product


@router.post("/products", response_model=ProductResponse)
def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new product."""
    product = Product(
        workspace_id=current_user.workspace_id,
        name=data.name,
        sku=data.sku,
        barcode=data.barcode,
        description=data.description,
        price=data.price,
        compare_at_price=data.compare_at_price,
        cost=data.cost,
        stock=data.stock,
        low_stock_threshold=data.low_stock_threshold,
        weight=data.weight,
        category=data.category,
        tags=json.dumps(data.tags) if data.tags else None,
        images=json.dumps(data.images) if data.images else None,
        status=data.status,
        sizes=data.sizes,
        colors=data.colors,
        meta_title=data.meta_title,
        meta_description=data.meta_description,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a product."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.workspace_id == current_user.workspace_id,
    ).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "tags" in update_data and update_data["tags"] is not None:
        update_data["tags"] = json.dumps(update_data["tags"])

    if "images" in update_data and update_data["images"] is not None:
        update_data["images"] = json.dumps(update_data["images"])

    for key, value in update_data.items():
        setattr(product, key, value)

    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a product by setting status to archivado."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.workspace_id == current_user.workspace_id,
    ).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")

    product.status = "archivado"
    product.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"Producto '{product.name}' archivado"}


# ===== CATEGORIES =====

@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all categories for the workspace."""
    categories = db.query(Category).filter(
        Category.workspace_id == current_user.workspace_id,
    ).order_by(Category.name.asc()).all()
    return categories


@router.post("/categories", response_model=CategoryResponse)
def create_category(
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new category."""
    existing = db.query(Category).filter(
        Category.workspace_id == current_user.workspace_id,
        Category.name == data.name,
    ).first()
    if existing:
        raise HTTPException(400, f"Ya existe una categoría con nombre '{data.name}'")

    category = Category(
        workspace_id=current_user.workspace_id,
        name=data.name,
        description=data.description,
        icon=data.icon,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a category."""
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.workspace_id == current_user.workspace_id,
    ).first()
    if not category:
        raise HTTPException(404, "Categoría no encontrada")

    category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.icon is not None:
        category.icon = data.icon

    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a category."""
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.workspace_id == current_user.workspace_id,
    ).first()
    if not category:
        raise HTTPException(404, "Categoría no encontrada")

    db.delete(category)
    db.commit()
    return {"ok": True, "message": f"Categoría '{category.name}' eliminada"}
