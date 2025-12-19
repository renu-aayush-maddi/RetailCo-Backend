from backend.db import AsyncSessionLocal
from backend import crud

async def check_product_availability(product_id: str):
    async with AsyncSessionLocal() as session:
        rows = await crud.get_inventory_for_product(session, product_id)

    stores = []

    for r in rows:
        available = max((r.stock or 0) - (r.reserved or 0), 0)
        if available > 0:
            stores.append({
                "store_id": r.store_id,
                "location": r.location,
                "available_qty": available
            })

    return {
        "product_id": product_id,
        "stores": stores
    }
