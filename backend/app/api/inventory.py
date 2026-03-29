from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas.schemas import ERPInventorySync, GenericResponse
from ..models.models import Product
from ..core.database import get_db

router = APIRouter()

@router.post("/inventory/sync-erp", response_model=GenericResponse)
async def erp_inventory_sync(
    sync_data: ERPInventorySync,
    db: Session = Depends(get_db)
):
    """
    Receives mass inventory updates from ERP systems (e.g., AS400).
    Updates existing products or creates new ones in the 'Inventario Base'.
    """
    updated_count = 0
    created_count = 0
    
    for item in sync_data.items:
        # Check if product exists by SKU
        product = db.query(Product).filter(Product.sku == item.sku).first()
        
        if product:
            product.stock_quantity = item.quantity
            if item.price:
                product.price = item.price
            product.name = item.name
            updated_count += 1
        else:
            new_product = Product(
                sku=item.sku,
                name=item.name,
                stock_quantity=item.quantity,
                price=item.price
            )
            db.add(new_product)
            created_count += 1
            
    db.commit()
    
    return {
        "status": "success", 
        "message": f"Sync completed. Created: {created_count}, Updated: {updated_count}. Source: {sync_data.source}"
    }
