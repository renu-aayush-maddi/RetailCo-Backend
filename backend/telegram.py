



# backend/telegram.py
import os
import json
import httpx
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from backend.db import AsyncSessionLocal
from backend import crud
from backend.agents.master_graph import run_master

load_dotenv()
router = APIRouter()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELE_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------- helpers ----------
async def telegram_send_message(chat_id: int, text: str, reply_markup: dict = None, parse_mode: str = None):
    url = TELE_API + "/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if parse_mode:
        payload["parse_mode"] = parse_mode
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload)
        print("[TELEGRAM] sendMessage:", r.status_code, r.text)
        try:
            return r.json()
        except Exception:
            return {"ok": False, "error": "invalid response"}

async def telegram_send_photo(chat_id: int, photo_url: str, caption: str = None, reply_markup: dict = None):
    url = TELE_API + "/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=payload)
        print("[TELEGRAM] sendPhoto:", r.status_code, r.text)
        return r.json()

def normalize_phone(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit() or ch == "+")

async def send_items_via_telegram(chat_id: int, items: list):
    for item in items:
        name = item.get("name")
        price = item.get("price")
        cat = item.get("category") or ""
        pid = item.get("product_id")
        image = item.get("image")
        caption = f"*{name}*\nPrice: ₹{price}\n{cat}\nID: {pid}"
        kb = {"inline_keyboard": [[{"text": "Buy", "callback_data": json.dumps({"action":"buy","product_id": pid})}]]}
        if image:
            await telegram_send_photo(chat_id, image, caption=caption, reply_markup=kb)
        else:
            await telegram_send_message(chat_id, caption, reply_markup=kb, parse_mode="Markdown")

ONBOARD_PROMPT = (
    "Hi! To link your Telegram to your account, please reply with your phone number "
    "(include country code, e.g. +919876543210). If you don't have an account, "
    "I'll create a guest account for you."
)

# ---------- webhook ----------
@router.post("/telegram/webhook")
async def telegram_webhook(req: Request, background: BackgroundTasks):
    try:
        body = await req.json()
    except Exception as e:
        print("[TELEGRAM] Failed to parse webhook JSON:", e)
        return JSONResponse(status_code=200, content={"ok": True})

    print(">>> TELEGRAM WEBHOOK HIT")
    print("[TELEGRAM] BODY:", body)

    # Handle text messages
    if "message" in body:
        msg = body["message"]
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()
        from_user = msg.get("from", {})
        tg_id = str(from_user.get("id"))

        async with AsyncSessionLocal() as db:
            user = await crud.get_user_by_telegram(db, tg_id)

            if not user:
                # onboarding flow
                if text and any(ch.isdigit() for ch in text):
                    phone = normalize_phone(text)
                    existing = await crud.get_user_by_phone(db, phone)
                    if existing:
                        await crud.link_telegram_to_user(db, existing.user_id, tg_id)
                        await telegram_send_message(chat_id, f"Thanks — linked to {existing.email or existing.name}. You can now chat.")
                        user = existing
                    else:
                        new_user = await crud.upsert_guest_user_by_telegram(db, tg_id, name=from_user.get("first_name"), phone=phone)
                        await telegram_send_message(chat_id, f"Guest account created and linked to {phone}. You can now chat.")
                        user = new_user
                else:
                    await telegram_send_message(chat_id, ONBOARD_PROMPT)
                    return {"ok": True}

            # at this point user is linked
            session_id = f"telegram:{tg_id}"
            background.add_task(handle_user_message, session_id, text, {"user_id": user.user_id}, chat_id)
            return {"ok": True}

    # Handle callback queries (inline Buy button)
    if "callback_query" in body:
        cb = body["callback_query"]
        data_raw = cb.get("data")
        chat_id = cb["message"]["chat"]["id"]
        from_user = cb["from"]
        tg_id = str(from_user.get("id"))

        # Ack callback
        async with httpx.AsyncClient() as client:
            await client.post(f"{TELE_API}/answerCallbackQuery", json={"callback_query_id": cb["id"]})

        try:
            data = json.loads(data_raw)
        except Exception:
            data = {"action": data_raw}

        if data.get("action") == "buy":
            pid = data.get("product_id")
            async with AsyncSessionLocal() as db:
                user = await crud.get_user_by_telegram(db, tg_id)
            if not user:
                await telegram_send_message(chat_id, "Please send your phone number first so we can link your account.")
                return {"ok": True}
            background.add_task(handle_buy, tg_id, pid, chat_id, user.user_id)
            return {"ok": True}

    return {"ok": True}

# ---------- background workers ----------
async def handle_user_message(session_id: str, text: str, user_meta: dict, chat_id: int):
    try:
        final = await run_master(session_id, text, user_meta)
        msg_text = final.get("results", {}).get("message", "")
        items = final.get("results", {}).get("items", [])

        if msg_text:
            await telegram_send_message(chat_id, msg_text)
        if items:
            await send_items_via_telegram(chat_id, items)

        async with AsyncSessionLocal() as db:
            try:
                await crud.create_chat_entry(db, user_meta["user_id"], session_id, "user", text, intent=final.get("intent"))
                if msg_text:
                    await crud.create_chat_entry(db, user_meta["user_id"], session_id, "assistant", msg_text, intent=final.get("intent"), results=final.get("results"))
            except Exception as e:
                print("[TELEGRAM] DB save error:", e)
    except Exception as e:
        print("[TELEGRAM] handle_user_message error:", e)
        await telegram_send_message(chat_id, "Sorry — I hit an error processing your request.")

async def handle_buy(tg_id: str, product_id: str, chat_id: int, user_id: str):
    session_id = f"telegram:{tg_id}"
    buy_text = f"buy {product_id}"
    try:
        final = await run_master(session_id, buy_text, {"user_id": user_id})
        msg = final.get("results", {}).get("message", "")
        await telegram_send_message(chat_id, msg or "Order flow completed.")
        async with AsyncSessionLocal() as db:
            try:
                await crud.create_chat_entry(db, user_id, session_id, "user", buy_text, intent=final.get("intent"))
                if msg:
                    await crud.create_chat_entry(db, user_id, session_id, "assistant", msg, intent=final.get("intent"), results=final.get("results"))
            except Exception as e:
                print("[TELEGRAM] DB save error:", e)
    except Exception as e:
        print("[TELEGRAM] handle_buy error:", e)
        await telegram_send_message(chat_id, "Sorry — could not complete the order.")
