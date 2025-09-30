from typing import Dict, Any
from backend.db import AsyncSessionLocal
from backend import crud
from sqlalchemy import select
from backend.models import Product

def _price_of(product: Dict[str, Any]) -> float:
    try:
        return float(product.get("price") or 0.0)
    except Exception:
        return 0.0

async def add_first_rec_to_cart(user_id: str, channel: str, first_rec: Dict[str, Any], qty: int = 1):
    async with AsyncSessionLocal() as session:
        cart = await crud.get_or_create_cart(session, user_id, channel)
        price = _price_of(first_rec)
        await crud.add_item_to_cart(session, cart.cart_id, first_rec.get("product_id"), price, qty, meta={"source":"rec_top1"})
        items = await crud.get_cart_items(session, cart.cart_id)
        subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
        return {
            "cart_id": cart.cart_id,
            "count": len(items),
            "subtotal": round(subtotal, 2)
        }

async def add_specific_to_cart(user_id: str, channel: str, product_id: str, qty: int = 1):
    async with AsyncSessionLocal() as session:
        cart = await crud.get_or_create_cart(session, user_id, channel)
        # fetch price from DB Product (fallback 0 if missing)
        r = await session.execute(select(Product).where(Product.product_id == product_id))
        p = r.scalar_one_or_none()
        price = float(p.price) if p and p.price is not None else 0.0
        await crud.add_item_to_cart(session, cart.cart_id, product_id, price, qty, meta={"source":"explicit_add"})
        items = await crud.get_cart_items(session, cart.cart_id)
        subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
        return {
            "cart_id": cart.cart_id,
            "count": len(items),
            "subtotal": round(subtotal, 2)
        }

async def get_cart_summary(user_id: str, channel: str):
    async with AsyncSessionLocal() as session:
        cart = await crud.get_or_create_cart(session, user_id, channel)
        items = await crud.get_cart_items(session, cart.cart_id)
        subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
        out_items = [{"cart_item_id": i.cart_item_id, "product_id": i.product_id, "qty": i.qty, "price": float(i.price_at_add)} for i in items]
        return {"cart_id": cart.cart_id, "items": out_items, "subtotal": round(subtotal, 2)}

async def remove_item(user_id: str, channel: str, cart_item_id: str):
    async with AsyncSessionLocal() as session:
        await crud.remove_cart_item(session, cart_item_id)
        cart = await crud.get_or_create_cart(session, user_id, channel)
        items = await crud.get_cart_items(session, cart.cart_id)
        subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
        return {"cart_id": cart.cart_id, "count": len(items), "subtotal": round(subtotal, 2)}
