
# backend/app.py

import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import json
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.agents.master_graph import run_master, get_active_session_for_user
from backend.deps import get_user_from_token 
from backend.profile_manual import router as manual_router
from backend.telegram import router as telegram_router
from backend.db import engine, Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend import crud
from jose import jwt, JWTError
from backend.agents.master_graph import redis as redis_client,clear_user_memory



@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title="OneSale Agentic Retail Backend - Neon Demo",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://coruscating-faun-e8a4fc.netlify.app",
    "https://retailco-sales.netlify.app"
    # add your deployed frontend domain(s) here
    # "https://yourapp.netlify.app",
    
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from backend import auth

app.include_router(auth.router)
app.include_router(telegram_router)
app.include_router(manual_router)

security = HTTPBearer(auto_error=False)

class ChatIn(BaseModel):
    session_id: Optional[str] = None
    text: str
    channel: Optional[str] = "web"

@app.post("/chat")
async def chat_endpoint(
    payload: ChatIn,
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
):
    # Canonicalize session to user:{uid}:{channel}
    channel = (payload.channel or "web").lower()
    incoming_sid = payload.session_id or f"user:{user_id}:{channel}"
    if not incoming_sid.startswith("user:"):
        incoming_sid = f"user:{user_id}:{channel}"

    user_meta = {"user_id": user_id}
    result = await run_master(incoming_sid, payload.text, user_meta)

    # persist history to DB (best effort)
    try:
        await crud.create_chat_entry(
            db, user_id, incoming_sid, "user", payload.text,
            intent=result.get("intent"), results=None
        )
        assistant_text = result["results"].get("message") or json.dumps(result.get("results", {}))
        await crud.create_chat_entry(
            db, user_id, incoming_sid, "assistant", assistant_text,
            intent=result.get("intent"), results=result.get("results")
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        print(f"[CHAT] history save error: {e}")

    return result

@app.get("/history/me")
async def my_history(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    rows = await crud.get_history_for_user(db, user_id, limit=limit)
    return [
        {
            "id": r.id, "role": r.role, "message": r.message,
            "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
        } for r in rows
    ]

@app.get("/history")
async def history_by_session(
    session_id: str = Query(..., description="e.g., user:{uid}:web"),
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    rows = await crud.get_history_for_session(db, session_id, limit=limit)
    return [
        {
            "id": r.id, "role": r.role, "message": r.message,
            "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
        } for r in rows
    ]

@app.get("/session/active")
async def get_active_session(channel: str = Query("web"), user_id: str = Depends(get_user_from_token)):
    """
    Returns canonical session id for the user/channel. The first /chat call will
    rehydrate from any previously active session automatically.
    """
    canonical = f"user:{user_id}:{channel}"
    # We return canonical to keep clients simple; cross-channel merge is handled in run_master
    return {"session_id": canonical}

@app.post("/session/reset")
async def reset_session(channel: str = Query("web"), user_id: str = Depends(get_user_from_token)):
    """
    Clears the current session envelope (but not the durable user profile).
    """
    from backend.agents.master_graph import save_session
    sid = f"user:{user_id}:{channel}"
    empty = {"session_id": sid, "memory": {}, "history": [], "last_updated": __import__("time").time()}
    await save_session(sid, empty, ttl_seconds=60*60*24*7)
    return {"ok": True, "session_id": sid}









############cart############################################
from pydantic import BaseModel
from typing import Optional
from backend.agents import cart_agent
from backend.agents.master_graph import load_session as load_session_from_redis

class CartAddIn(BaseModel):
    product_id: Optional[str] = None
    from_first_rec: Optional[bool] = False
    qty: Optional[int] = 1
    channel: Optional[str] = "web"
    
@app.post("/cart/add")
async def cart_add(
    payload: CartAddIn,
    user_id: str = Depends(get_user_from_token),
):
    channel = (payload.channel or "web").lower()
    if payload.from_first_rec:
        sid = f"user:{user_id}:{channel}"
        s = await load_session_from_redis(sid)
        last = (s.get("history") or [])[-1] if (s.get("history")) else None
        recs = ((last or {}).get("results") or {}).get("recommendations", {}).get("recs", []) if last else []
        if not recs:
            raise HTTPException(status_code=400, detail="No recommendations to add.")
        summary = await cart_agent.add_first_rec_to_cart(user_id, channel, recs[0], qty=payload.qty or 1)
        return {"ok": True, "cart": summary}
    else:
        if not payload.product_id:
            raise HTTPException(status_code=400, detail="product_id required")
        summary = await cart_agent.add_specific_to_cart(user_id, channel, payload.product_id, qty=payload.qty or 1)
        return {"ok": True, "cart": summary}

@app.get("/cart/summary")
async def cart_summary(
    channel: str = Query("web"),
    user_id: str = Depends(get_user_from_token),
):
    summary = await cart_agent.get_cart_summary(user_id, channel.lower())
    return {"ok": True, "cart": summary}

@app.delete("/cart/item/{cart_item_id}")
async def cart_remove_item(
    cart_item_id: str,
    channel: str = Query("web"),
    user_id: str = Depends(get_user_from_token),
):
    summary = await cart_agent.remove_item(user_id, channel.lower(), cart_item_id)
    return {"ok": True, "cart": summary}


@app.get("/health")
async def health():
    return {"status": "ok"}


from backend.agents.payment_agent import process_checkout_db
import time

class PaymentIntentIn(BaseModel):
    payment_intent_id: str

@app.post("/payment/confirm")
async def payment_confirm(
    payload: PaymentIntentIn,
    user_id: str = Depends(get_user_from_token),
):
    key = f"payment_intent:{payload.payment_intent_id}"
    raw = await redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="Payment intent not found or expired")

    intent = json.loads(raw)
    now = int(time.time())
    expires_at = int(intent.get("expires_at") or 0)

    # Prevent double confirmation
    status = intent.get("status")
    if status != "pending":
        return {"status": status, "message": "This payment intent is no longer pending."}

    # Check expiry
    if now > expires_at:
        intent["status"] = "expired"
        await redis_client.set(key, json.dumps(intent), ex=60)
        return {"status": "expired", "message": "Payment window expired. Regenerate QR to continue."}

    # Defensive amount read
    amount = float(intent.get("amount") or intent.get("final_amount") or intent.get("final_paid_amount") or 0.0)
    product_id = intent.get("product_id") or intent.get("sku")
    qty = int(intent.get("qty", 1) or 1)
    use_loyalty = intent.get("use_loyalty") if "use_loyalty" in intent else None
    result = await process_checkout_db(
    user_id=user_id,
    product_id=intent.get("product_id") or intent.get("sku"),
    amount=float(intent.get("amount") or intent.get("final_amount") or intent.get("final_paid_amount") or 0.0),
    store_id="S1",
    qty=int(intent.get("qty", 1) or 1),
    use_loyalty=use_loyalty,
    payment_intent_id=payload.payment_intent_id,
)

 
    try:
        raw2 = await redis_client.get(key)
        if raw2:
            latest_intent = json.loads(raw2)
            # ensure status reflects result
            if result.get("status") == "success":
                latest_intent["status"] = "success"
                latest_intent["order_id"] = result.get("order_id")
                latest_intent["final_paid_amount"] = result.get("final_amount")
                latest_intent["paid_at"] = int(time.time())
            else:
                latest_intent["status"] = result.get("status") or "error"
                latest_intent["error"] = result.get("error")
            await redis_client.set(key, json.dumps(latest_intent), ex=300)
    except Exception:
        pass

    if result.get("status") == "success":
        return {"status": "success", "order": {"order_id": result.get("order_id")}, "message": "Payment successful and order confirmed!"}
    else:
        return {"status": result.get("status"), "message": result.get("error") or "Payment processing failed."}


@app.post("/payment/regenerate")
async def payment_regenerate(
    payload: PaymentIntentIn,
    user_id: str = Depends(get_user_from_token),
):
    key = f"payment_intent:{payload.payment_intent_id}"
    raw = await redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="Payment intent not found or expired")

    intent = json.loads(raw)

    # If already successful, nothing to regenerate
    if intent.get("status") == "success":
        return {"status": "success", "message": "This payment is already successful. No need to regenerate QR."}

    now = int(time.time())
    new_expires_at = now + 120

    # Defensive amount read for regen
    amount = float(intent.get("amount") or intent.get("final_amount") or intent.get("final_paid_amount") or 0.0)
    pid = payload.payment_intent_id

    new_qr = f"upi://pay?pa=retailco@upi&am={amount:.2f}&tn=RetailCo%20Order%20{pid}"

    intent["status"] = "pending"
    intent["expires_at"] = new_expires_at
    # update created_at to now for clarity
    intent["created_at"] = now

    await redis_client.set(key, json.dumps(intent), ex=180)

    return {
        "status": "pending",
        "qr_data": new_qr,
        "expires_at": new_expires_at,
        "message": "Here is a fresh QR code. Please complete the payment within 2 minutes."
    }
    
    
@app.delete("/history/clear")
async def clear_history_and_cache(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
):
    """
    SOFT RESET:
    1. Wipes Redis (Forget current conversation stage/context)
    2. Wipes DB Chat Logs (Clean UI)
    3. PRESERVES Carts & Reservations
    """
    try:
        # 1. Clear Redis
        await clear_user_memory(user_id)

        # 2. Clear SQL Chat Logs only
        await crud.delete_chat_history(db, user_id)
        await db.commit()

        return {
            "status": "success", 
            "message": "Chat history and session context cleared. Cart and reservations are safe."
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
