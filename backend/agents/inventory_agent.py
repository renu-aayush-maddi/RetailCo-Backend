# backend/agents/inventory_agent.py
"""
Inventory agent with two modes:
 - DB-backed async functions: check_stock_db, reserve_stock_db (recommended for Neon/Postgres)
 - Local file fallback functions: check_stock_local, reserve_stock_local (used if DB not configured)
"""

import json
from pathlib import Path
from typing import Dict, Optional

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INV_FILE = DATA_DIR / "inventory.json"

# local file cache (fallback)
def load_inventory():
    with open(INV_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

INV_CACHE = load_inventory()

def check_stock_local(product_id: str, store_id: str = "S1") -> Dict:
    for rec in INV_CACHE:
        if rec["product_id"] == product_id and rec["store_id"] == store_id:
            return {"stock": rec["stock"], "reserved": rec.get("reserved", 0)}
    return {"stock": 0, "reserved": 0}

def reserve_stock_local(product_id: str, store_id: str = "S1", qty: int = 1) -> bool:
    for rec in INV_CACHE:
        if rec["product_id"] == product_id and rec["store_id"] == store_id:
            if rec["stock"] - rec.get("reserved", 0) >= qty:
                rec["reserved"] = rec.get("reserved", 0) + qty
                return True
    return False

# --- DB-backed inventory (async) ---
try:
    from backend.db import AsyncSessionLocal  # async session factory
    from backend import crud as db_crud
    DB_AVAILABLE = True
except Exception as e:
    print(f"[INVENTORY] DB imports failed: {e}")
    DB_AVAILABLE = False

async def check_stock_db(product_id: str, store_id: str = "S1") -> Dict:
    """
    Query DB inventory for product_id/store_id.
    Returns dict with keys: stock, reserved
    """
    if not DB_AVAILABLE:
        return check_stock_local(product_id, store_id)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from backend.models import Inventory
        q = select(Inventory).where(Inventory.product_id == product_id, Inventory.store_id == store_id)
        r = await session.execute(q)
        rec = r.scalar_one_or_none()
        if not rec:
            return {"stock": 0, "reserved": 0}
        return {"stock": int(rec.stock or 0), "reserved": int(rec.reserved or 0)}

async def reserve_stock_db(product_id: str, store_id: str = "S1", qty: int = 1) -> bool:
    """
    Attempt to atomically reserve `qty` units of product_id at store_id.
    Uses crud.check_and_reserve(session, product_id, store_id, qty) which performs
    an update in a DB transaction.
    """
    if not DB_AVAILABLE:
        return reserve_stock_local(product_id, store_id, qty)
    async with AsyncSessionLocal() as session:
        try:
            print(f"[INVENTORY] reserve_stock_db calling check_and_reserve for {product_id}")
            ok = await db_crud.check_and_reserve(session, product_id, store_id, qty)
            print(f"[INVENTORY] reserve_stock_db returned: {ok}")
            return bool(ok)
        except Exception as e:
            print(f"[INVENTORY] reserve_stock_db error: {e}")
            return False
