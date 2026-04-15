"""ERP inventory sync endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..models.product import Product
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class InventoryItem(BaseModel):
    sku: str
    name: str
    quantity: int
    price: Optional[float] = None


class ERPInventorySync(BaseModel):
    source: str = "erp"
    items: list[InventoryItem] = []


@router.post("/inventory/sync-erp")
async def erp_inventory_sync(
    sync_data: ERPInventorySync,
    db: Session = Depends(get_db),
):
    """Receive mass inventory updates from ERP systems."""
    updated_count = 0
    created_count = 0

    for item in sync_data.items:
        product = db.query(Product).filter(Product.sku == item.sku).first()

        if product:
            product.stock = item.quantity
            if item.price:
                product.price = item.price
            product.name = item.name
            updated_count += 1
        else:
            new_product = Product(
                workspace_id=1,  # TODO: derive from auth
                sku=item.sku,
                name=item.name,
                stock=item.quantity,
                price=item.price or 0.0,
            )
            db.add(new_product)
            created_count += 1

    db.commit()
    return {
        "status": "success",
        "message": f"Sync completado. Creados: {created_count}, Actualizados: {updated_count}. Fuente: {sync_data.source}",
    }
