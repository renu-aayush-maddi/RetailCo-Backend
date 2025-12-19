
# backend/agents/payment_agent.py
import uuid
import json
import time
from typing import Dict, Any, Optional

def process_payment_mock(user_id: str, amount: float, card: dict = None) -> Dict[str, Any]:
    payment_id = "PMT-" + uuid.uuid4().hex[:8]
    return {"status": "success", "payment_id": payment_id, "amount": amount}

try:
    from backend.db import AsyncSessionLocal
    from backend import crud as db_crud
    # Use the redis instance from master_graph for a single source of truth
    from backend.agents.master_graph import redis as redis_client
    DB_AVAILABLE = True
except Exception as e:
    print(f"[PAYMENT] DB imports failed: {e}")
    DB_AVAILABLE = False

async def process_checkout_db(
    user_id: Optional[str],
    product_id: str,
    amount: float,
    store_id: str = "S1",
    qty: int = 1,
    use_loyalty: Optional[bool] = None,
    payment_intent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    High-level checkout with loyalty support:
      - reserve stock (db_crud.check_and_reserve)
      - optionally apply loyalty redeem BEFORE payment (db_crud.apply_loyalty_redeem)
      - simulate/process payment (process_payment_mock)
      - create order (db_crud.create_order)
      - award loyalty points AFTER successful payment (db_crud.apply_loyalty_earn)
      - update redis payment intent (if payment_intent_id provided)
    """
    print(f"[PAYMENT] process_checkout_db called user={user_id} product={product_id} amount={amount} qty={qty} use_loyalty={use_loyalty} intent={payment_intent_id}")

    if not DB_AVAILABLE:
        # Local fallback: still simulate loyalty effects for testing (no DB writes)
        # If you want to skip loyalty logic when DB not available, set use_loyalty=False here.
        final_amount = float(amount)
        discount_applied = 0.0
        points_used = 0
        # simulate payment
        payment = process_payment_mock(user_id or "anonymous", final_amount)
        order_id = "ORD-" + uuid.uuid4().hex[:8]
        return {"status": "success", "order_id": order_id, "payment": payment, "final_amount": final_amount}

    key = f"payment_intent:{payment_intent_id}" if payment_intent_id else None
    now = int(time.time())

    async with AsyncSessionLocal() as session:
        # 1) Reserve inventory
        try:
            reserved = await db_crud.check_and_reserve(session, product_id, store_id, qty)
        except Exception as e:
            print(f"[PAYMENT] check_and_reserve raised exception: {e}")
            # mark intent if present
            if key:
                try:
                    raw = await redis_client.get(key)
                    if raw:
                        intent = json.loads(raw)
                        intent["status"] = "reserve_error"
                        intent["error"] = str(e)
                        await redis_client.set(key, json.dumps(intent), ex=300)
                except Exception:
                    pass
            return {"status": "error", "error": "reserve_exception", "details": str(e)}

        if not reserved:
            # no stock
            if key:
                try:
                    raw = await redis_client.get(key)
                    if raw:
                        intent = json.loads(raw)
                        intent["status"] = "out_of_stock"
                        await redis_client.set(key, json.dumps(intent), ex=60)
                except Exception:
                    pass
            return {"status": "error", "error": "out_of_stock"}

        # 2) Loyalty redeem (before payment) - returns (discount, points_used, remaining_points)
        discount_applied = 0.0
        points_used = 0
        remaining_points = 0
        if use_loyalty and user_id:
            try:
                discount_applied, points_used, remaining_points = await db_crud.apply_loyalty_redeem(session, user_id, float(amount))
                # recompute final amount after discount
                final_amount = float(max(0.0, float(amount) - float(discount_applied)))
            except Exception as e:
                print(f"[PAYMENT] apply_loyalty_redeem failed: {e}")
                final_amount = float(amount)
        else:
            final_amount = float(amount)

        # 3) Process payment (mock)
        payment = process_payment_mock(user_id or "anonymous", final_amount)

        # 4) Create order record in DB
        items = [{"product_id": product_id, "qty": qty, "unit_price": float(final_amount) / max(qty, 1)}]
        try:
            order_id = await db_crud.create_order(session, user_id or "anonymous", items, float(final_amount), fulfillment="ship")
        except Exception as e:
            print(f"[PAYMENT] create_order failed: {e}")
            # Rollback reservation? (reserved stays increased: you might want to add logic to release reservation)
            if key:
                try:
                    raw = await redis_client.get(key)
                    if raw:
                        intent = json.loads(raw)
                        intent["status"] = "order_create_failed"
                        intent["error"] = str(e)
                        await redis_client.set(key, json.dumps(intent), ex=300)
                except Exception:
                    pass
            return {"status": "error", "error": "order_create_failed", "details": str(e)}

        # 5) Award loyalty points based on final paid amount
        try:
            if user_id:
                await db_crud.apply_loyalty_earn(session, user_id, float(final_amount))
        except Exception as e:
            print(f"[PAYMENT] apply_loyalty_earn failed: {e}")
            # not fatal for order, but log it and update intent
            if key:
                try:
                    raw = await redis_client.get(key)
                    if raw:
                        intent = json.loads(raw)
                        intent.setdefault("warnings", []).append(f"apply_loyalty_earn_failed:{str(e)}")
                        await redis_client.set(key, json.dumps(intent), ex=300)
                except Exception:
                    pass

        # 6) Update Redis payment intent (success)
        if key:
            try:
                raw = await redis_client.get(key)
                if raw:
                    intent = json.loads(raw)
                else:
                    intent = {}
                intent["status"] = "success"
                intent["order_id"] = order_id
                intent["final_paid_amount"] = float(final_amount)
                intent["paid_at"] = now
                intent["points_used"] = int(points_used)
                intent["loyalty_discount"] = float(discount_applied)
                await redis_client.set(key, json.dumps(intent), ex=60 * 60)
            except Exception as e:
                print(f"[PAYMENT] failed to update redis intent: {e}")

        return {
            "status": "success",
            "order_id": order_id,
            "payment": payment,
            "final_amount": float(final_amount),
            "points_used": int(points_used),
            "loyalty_discount": float(discount_applied),
        }


# # backend/agents/payment_agent.py
# import uuid
# import json
# import time
# from typing import Dict, Any, Optional

# def process_payment_mock(user_id: str, amount: float, card: dict = None) -> Dict[str, Any]:
#     payment_id = "PMT-" + uuid.uuid4().hex[:8]
#     return {"status": "success", "payment_id": payment_id, "amount": amount}

# try:
#     from backend.db import AsyncSessionLocal
#     from backend import crud as db_crud
#     from backend.agents.master_graph import redis as redis_client
#     DB_AVAILABLE = True
# except Exception as e:
#     print(f"[PAYMENT] DB imports failed: {e}")
#     DB_AVAILABLE = False

# async def process_checkout_db(
#     user_id: Optional[str],
#     product_id: str,
#     amount: float,
#     store_id: str = "S1",
#     qty: int = 1,
#     use_loyalty: Optional[bool] = None,
#     payment_intent_id: Optional[str] = None,
# ) -> Dict[str, Any]:
#     """
#     High-level checkout:
#       - reserve stock
#       - apply loyalty
#       - create order
#       - CONFIRM STOCK DEDUCTION (The Fix)
#       - CLEAR CART (The Fix)
#     """
#     print(f"[PAYMENT] process_checkout_db called user={user_id} product={product_id} amount={amount} qty={qty} intent={payment_intent_id}")

#     if not DB_AVAILABLE:
#         # Local fallback
#         final_amount = float(amount)
#         payment = process_payment_mock(user_id or "anonymous", final_amount)
#         order_id = "ORD-" + uuid.uuid4().hex[:8]
#         return {"status": "success", "order_id": order_id, "payment": payment, "final_amount": final_amount}

#     key = f"payment_intent:{payment_intent_id}" if payment_intent_id else None
#     now = int(time.time())

#     async with AsyncSessionLocal() as session:
#         # 1) Reserve inventory (Temporary)
#         try:
#             reserved = await db_crud.check_and_reserve(session, product_id, store_id, qty)
#         except Exception as e:
#             print(f"[PAYMENT] check_and_reserve raised exception: {e}")
#             if key:
#                 await _update_intent_error(key, "reserve_error", str(e))
#             return {"status": "error", "error": "reserve_exception", "details": str(e)}

#         if not reserved:
#             if key:
#                 await _update_intent_error(key, "out_of_stock", "No stock available")
#             return {"status": "error", "error": "out_of_stock"}

#         # 2) Loyalty redeem
#         discount_applied = 0.0
#         points_used = 0
#         if use_loyalty and user_id:
#             try:
#                 discount_applied, points_used, _ = await db_crud.apply_loyalty_redeem(session, user_id, float(amount))
#                 final_amount = float(max(0.0, float(amount) - float(discount_applied)))
#             except Exception as e:
#                 print(f"[PAYMENT] apply_loyalty_redeem failed: {e}")
#                 final_amount = float(amount)
#         else:
#             final_amount = float(amount)

#         # 3) Process payment
#         payment = process_payment_mock(user_id or "anonymous", final_amount)

#         # 4) Create order
#         items = [{"product_id": product_id, "qty": qty, "unit_price": float(final_amount) / max(qty, 1)}]
#         try:
#             order_id = await db_crud.create_order(session, user_id or "anonymous", items, float(final_amount), fulfillment="ship")
            
#             # ✅ FIX: Finalize Inventory (Convert reservation to sold)
#             await db_crud.confirm_stock_deduction(session, product_id, store_id, qty)
            
#         except Exception as e:
#             print(f"[PAYMENT] create_order failed: {e}")
#             if key:
#                 await _update_intent_error(key, "order_create_failed", str(e))
#             return {"status": "error", "error": "order_create_failed", "details": str(e)}

#         # 5) Award loyalty points
#         try:
#             if user_id:
#                 await db_crud.apply_loyalty_earn(session, user_id, float(final_amount))
#         except Exception as e:
#             print(f"[PAYMENT] apply_loyalty_earn failed: {e}")

#         # 6) ✅ FIX: Clear Cart
#         if user_id:
#             try:
#                 cart = await db_crud.get_or_create_cart(session, user_id, "web")
#                 if cart:
#                     print(f"[PAYMENT] Clearing cart {cart.cart_id}")
#                     await db_crud.clear_cart(session, cart.cart_id)
#             except Exception as e:
#                 print(f"[PAYMENT] Failed to clear cart: {e}")

#         # 7) Update Redis
#         if key:
#             try:
#                 raw = await redis_client.get(key)
#                 if raw:
#                     intent = json.loads(raw)
#                 else:
#                     intent = {}
#                 intent["status"] = "success"
#                 intent["order_id"] = order_id
#                 intent["final_paid_amount"] = float(final_amount)
#                 intent["paid_at"] = now
#                 intent["points_used"] = int(points_used)
#                 intent["loyalty_discount"] = float(discount_applied)
#                 await redis_client.set(key, json.dumps(intent), ex=60 * 60)
#             except Exception as e:
#                 print(f"[PAYMENT] failed to update redis intent: {e}")

#         return {
#             "status": "success",
#             "order_id": order_id,
#             "payment": payment,
#             "final_amount": float(final_amount),
#             "points_used": int(points_used),
#             "loyalty_discount": float(discount_applied),
#         }

# async def _update_intent_error(key, status, error_msg):
#     try:
#         raw = await redis_client.get(key)
#         if raw:
#             intent = json.loads(raw)
#             intent["status"] = status
#             intent["error"] = error_msg
#             await redis_client.set(key, json.dumps(intent), ex=300)
#     except Exception:
#         pass