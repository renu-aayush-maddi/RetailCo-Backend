# backend/agents/payment_agent.py
"""
Payment agent: mock payment and DB-backed order creation.
- process_payment_mock: simulates a payment (always succeeds in demo)
- process_checkout_db: reserves inventory (DB) + processes payment + creates order row in DB
"""

import uuid
from typing import Dict, Any

def process_payment_mock(user_id: str, amount: float, card: dict = None) -> Dict[str, Any]:
    payment_id = "PMT-" + uuid.uuid4().hex[:8]
    return {"status": "success", "payment_id": payment_id, "amount": amount}

# DB-backed orchestrator for checkout
try:
    # absolute imports so these resolve when running uvicorn backend.app:app
    from backend.db import AsyncSessionLocal
    from backend import crud as db_crud
    DB_AVAILABLE = True
except Exception as e:
    print(f"[PAYMENT] DB imports failed: {e}")
    DB_AVAILABLE = False

async def process_checkout_db(user_id: str, product_id: str, amount: float, store_id: str = "S1", qty: int = 1) -> Dict[str, Any]:
    """
    High-level checkout:
      1) attempt to reserve inventory using db_crud.check_and_reserve
      2) if reserved -> simulate payment (process_payment_mock)
      3) create order row in DB via db_crud.create_order
    """
    print(f"[PAYMENT] process_checkout_db called for user={user_id}, product={product_id}, amount={amount}, store={store_id}, qty={qty}")
    if not DB_AVAILABLE:
        print("[PAYMENT] DB not available, falling back to local flow")
        payment = process_payment_mock(user_id or "anonymous", amount)
        order_id = "ORD-" + uuid.uuid4().hex[:8]
        return {"status": "success", "order_id": order_id, "payment": payment, "product_id": product_id}

    async with AsyncSessionLocal() as session:
        # 1) Reserve
        try:
            reserved = await db_crud.check_and_reserve(session, product_id, store_id, qty)
        except Exception as e:
            print(f"[PAYMENT] check_and_reserve raised exception: {e}")
            return {"status":"error","error":"reserve_exception","details":str(e)}
        print(f"[PAYMENT] check_and_reserve returned: {reserved}")
        if not reserved:
            return {"status": "error", "error":"out_of_stock"}
        # 2) Payment (mock)
        payment = process_payment_mock(user_id or "anonymous", amount)
        # 3) Create order record
        items = [{"product_id": product_id, "qty": qty, "price": float(amount)}]
        try:
            order_id = await db_crud.create_order(session, user_id or "anonymous", items, float(amount), fulfillment="ship")
        except Exception as e:
            print(f"[PAYMENT] create_order failed: {e}")
            return {"status":"error","error":"order_create_failed","details":str(e)}
        print(f"[PAYMENT] order created: {order_id}")
        return {"status":"success", "order_id": order_id, "payment": payment}
