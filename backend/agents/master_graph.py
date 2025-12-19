# # backend/agents/master_graph.py
# ########################## human like ###########################
# import os
# import json
# import uuid
# import time
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()
# import traceback

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# from . import rec_agent, inventory_agent, payment_agent, cart_agent


# from sqlalchemy import text




# from backend.db import AsyncSessionLocal
# from backend import crud as db_crud

# from backend.agents.base import Node, NodeResult



# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node
        
# class LoyaltyAgentNode(Node):
#     def __init__(self, id: str = "loyalty_agent"):
#         super().__init__(id)

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_id = ctx.get("user_id")

#         # If there is no logged-in user, return zeroed-out loyalty info
#         if not user_id:
#             return NodeResult({
#                 "points": 0,
#                 "points_value": 0.0,
#                 "tier": "Bronze",
#                 "total_spend": 0.0,
#                 "promo": None,
#             })

#         # Use your real DB-backed helper from crud.py
#         async with AsyncSessionLocal() as session:
#             info = await db_crud.get_user_loyalty(session, user_id)

#         points = info.get("points", 0)
#         total_spend = float(info.get("total_spend", 0.0) or 0.0)
#         tier = info.get("tier") or "Bronze"
#         points_value = points * 0.5  # ₹ value per point

#         # Optional promo stub – you can customize or remove this
#         promo = {
#             "code": "WEDDING10",
#             "description": "10% off on wedding outfits",
#             "discount_pct": 10,
#         }

#         return NodeResult({
#             "points": points,
#             "points_value": points_value,
#             "tier": tier,
#             "total_spend": total_spend,
#             "promo": promo,
#         })



# SESSION_PREFIX = "session:"
# USER_ACTIVE_KEY_PREFIX = "user_active_session:"
# USER_PROFILE_PREFIX = "user_profile:"


# # ===============================
# # HARD FLOW STATES (SOURCE OF TRUTH)
# # ===============================
# STAGES = {
#     "RECOMMEND": "recommend",
#     "PRODUCT_DETAILS": "product_details",
#     "AVAILABILITY": "availability",
#     "RESERVE": "reserve_in_store",
#     "CART": "cart",
#     "CHECKOUT": "checkout",
#     "PAYMENT": "payment",
#     "ORDER_CONFIRMED": "order_confirmed"
# }



# async def load_session(session_id: str) -> Dict[str, Any]:
#     key = SESSION_PREFIX + session_id
#     raw = await redis.get(key)
#     if not raw:
#         return {"session_id": session_id, "memory": {}, "history": []}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {"session_id": session_id, "memory": {}, "history": []}


# async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24 * 7):
#     key = SESSION_PREFIX + session_id
#     await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


# async def get_active_session_for_user(user_id: Optional[str]) -> Optional[str]:
#     if not user_id:
#         return None
#     return await redis.get(USER_ACTIVE_KEY_PREFIX + user_id)


# async def set_active_session_for_user(user_id: Optional[str], session_id: str, ttl_seconds: int = 60 * 60 * 24 * 7):
#     if not user_id:
#         return
#     await redis.set(USER_ACTIVE_KEY_PREFIX + user_id, session_id, ex=ttl_seconds)


# async def merge_sessions(from_sid: Optional[str], into_sid: Optional[str], keep_last: int = 10):
#     if not from_sid or not into_sid or from_sid == into_sid:
#         return
#     old = await load_session(from_sid)
#     new = await load_session(into_sid)
#     merged = {
#         "session_id": into_sid,
#         "memory": {**(old.get("memory") or {}), **(new.get("memory") or {})},
#         "history": ((old.get("history") or []) + (new.get("history") or []))[-keep_last:],
#         "last_updated": __import__("time").time()
#     }
#     await save_session(into_sid, merged)
    



# async def load_user_profile(user_id: Optional[str]) -> Dict[str, Any]:
#     if not user_id:
#         return {}
#     raw = await redis.get(USER_PROFILE_PREFIX + user_id)
#     if not raw:
#         return {}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {}


# async def save_user_profile(user_id: Optional[str], patch: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24 * 90):
#     if not user_id or not isinstance(patch, dict):
#         return
#     key = USER_PROFILE_PREFIX + user_id
#     cur = await load_user_profile(user_id)
#     cur.update({k: v for k, v in patch.items() if v is not None})
#     await redis.set(key, json.dumps(cur), ex=ttl_seconds)

# class LLMAgentNode(Node):
#     def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
#         super().__init__(id)
#         available_agents = [
#     "rec_agent",
#     "inventory_agent",
#     "cart_agent",
#     "payment_agent",
#     "order_agent",
#     "loyalty_agent",
#     "fulfillment_agent",
#     "postpurchase_agent",
# ]
#         agents_text = ", ".join(available_agents)
        
#         self.system_prompt = system_prompt or """
# You are "Aura," a Top-Tier Retail Sales Associate for a premium fashion brand. 
# RESPOND IN JSON ONLY.

# AVAILABLE_AGENTS: rec_agent, inventory_agent, cart_agent, payment_agent, order_agent, loyalty_agent, fulfillment_agent, postpurchase_agent

# ──────────────────────────────────────────────────────────────
# 🧠 SALES PSYCHOLOGY & BEHAVIOR (CRITICAL)
# ──────────────────────────────────────────────────────────────
# 1. NEVER be a "Vending Machine". Do not just dump product lists immediately unless the user is very specific.
# 2. THE CONSULTATIVE LOOP:
#    - If user says "Show me shirts": 
#      ❌ Bad: "Here are 5 shirts."
#      ✅ Good: "I'd love to help! Are you looking for something formal for work, or a casual weekend vibe?"
#    - Ask ONE clarifying question at a time (Occasion, Fit, Fabric, or Color).

# 3. THE UPSELL (Cross-Selling):
#    - If the user selects a Product (e.g., a Suit), suggest a complement (e.g., a Tie or Pocket Square) before checkout.
#    - Use phrases like: "That jacket is a great choice. It pairs perfectly with these chinos..."

# 4. CONTEXT AWARENESS:
#    - Check UserProfile.city. If they are in "Guntur", prioritize mentions of the Guntur store.
#    - If UserProfile.loyalty_points > 1000, mention they have points to redeem.

# ──────────────────────────────────────────────────────────────
# MEMORY & TRUTH SOURCE
# ──────────────────────────────────────────────────────────────
# Use SessionMemory.profile + ConversationHistory as the SINGLE source of truth.
# If information is already present in memory (e.g., size, city), DO NOT ask for it again.

# ──────────────────────────────────────────────────────────────
# PRODUCT SELECTION & IDENTIFICATION RULES
# ──────────────────────────────────────────────────────────────
# User signals for selection: "this looks good", "give me details", "I want this", "add this".

# When product intent is detected, you MUST output:
# "meta": {
#   "sku": "<product_id>",
#   "confirm_selection": true
# }

# Set intent = "buy" but ready_to_buy = false initially.

# ──────────────────────────────────────────────────────────────
# PRODUCT ATTRIBUTE RESOLUTION
# ──────────────────────────────────────────────────────────────
# When a product is selected, check its `attributes` (size/color).
# - Ask ONLY for missing REQUIRED attributes.
# - Present options EXACTLY as provided in the product data.
# - Once attributes are resolved, transition to Fulfillment.

# ──────────────────────────────────────────────────────────────
# FULFILLMENT & INVENTORY
# ──────────────────────────────────────────────────────────────
# After attributes are resolved, ask:
# “Would you like to reserve it in store to try, or ship it to your address?”
# (Do not default to shipping if the user is near a store).

# ──────────────────────────────────────────────────────────────
# CART ACTION RULES
# ──────────────────────────────────────────────────────────────
# Trigger cart actions ONLY on explicit phrases like "add to cart" or "buy now".
# - Include "cart_agent" in plan.
# - Set meta.add = "product_id".

# ──────────────────────────────────────────────────────────────
# CHECKOUT & LOYALTY RULES
# ──────────────────────────────────────────────────────────────
# For checkout intent:
# - ready_to_buy = true
# - Include "payment_agent" in plan.

# If user has loyalty points and hasn't decided to use them:
# - Ask: "Would you like to redeem your loyalty points for this order?" in ask[].
# - Do NOT generate QR code yet.

# Only after user confirms payment details:
# - Set slots.confirm_payment = true.

# ──────────────────────────────────────────────────────────────
# PRODUCT DETAIL INTENT
# ──────────────────────────────────────────────────────────────
# If user asks to see details/features of a selected product:
# - Set meta.show_product_details = true.
# - Do NOT initiate checkout yet.

# ──────────────────────────────────────────────────────────────
# STRICT JSON OUTPUT SCHEMA
# ──────────────────────────────────────────────────────────────
# {
#   "intent": "recommend" | "buy" | "postpurchase" | "other" | "profile" | "qualify",
#   "plan": ["string"],
#   "message": "string",
#   "ask": ["string"],

#   "slots": {
#     "occasion": null | "string",
#     "size": null | "string",
#     "fit": null | "string",
#     "color_preference": null | "string",
#     "budget": null | "number",
#     "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
#     "payment_method": null | "upi" | "card" | "pos",
#     "preferred_store": null | "string",
#     "use_loyalty": null | "boolean",
#     "confirm_payment": null | "boolean",
#     "city": null | "string"
#   },

#   "ready_to_buy": "boolean",

#   "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "checkout" | "loyalty" | "payment" | "confirm",

#   "plan_notes": "string",

#   "meta": {
#     "rec_query": null | "string",
#     "sku": null | "string",
#     "qty": null | "number",
#     "confirm_selection": null | "boolean",
#     "add": null | "string",
#     "product_id": null | "string",
#     "profile": null | "object",
#     "show_product_details": null | "boolean",
#     "check_availability": null | "boolean",
#     "upsell_trigger": null | "boolean"
#   }
# }
# ──────────────────────────────────────────────────────────────
# OUTPUT RULES
# ──────────────────────────────────────────────────────────────
# - Message: Short, persuasive, consultative.
# - Ask: Max 1 question at a time.
# """


#         self.timeout = timeout

#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 500
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]

#     async def call_groq(self, prompt: str) -> str:
#         if not GROQ_API_KEY:
#             raise RuntimeError("GROQ_API_KEY not set")

#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
#         print("groq is called")
#         payload = {
#             "model": "llama-3.3-70b-versatile",          # or "llama-3.1-8b-instant"
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 500,
#             # strongly recommended since you expect strict JSON:
#             "response_format": {"type": "json_object"}
#         }

#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post(
#                 "https://api.groq.com/openai/v1/chat/completions",  # <- correct base + path
#                 headers=headers,
#                 json=payload,
#             )
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]


#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         history = ctx.get("history", []) or []
#         recent_history = history[-10:]
#         retrieved = await rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
#         fewshot = {
#             "intent": "recommend",
#             "plan": ["rec_agent"],
#             "message": "Here are some products you might like.",
#             "ask": ["Would you like to see details for any of these?"],
#             "slots": {"occasion": None,"size": None,"fit": None,"color_preference": None,"budget": None,"fulfillment": None,"payment_method": None,"preferred_store": None,"phone_or_whatsapp_ok": None},
#             "ready_to_buy": False,
#             "next_stage": "qualify",
#             "plan_notes": "collect slots before checkout",
#             "meta": {"rec_query": "men shirt"}
#         }
#         prompt = (
#             f"SessionMemory: {json.dumps(session_memory)}\n"
#             f"ConversationHistory: {json.dumps(recent_history)}\n"
#             f"RetrievedProducts: {json.dumps(retrieved)}\n\n"
#             f"ExampleJSON:\n{json.dumps(fewshot)}\n\n"
#             f"User: {user_text}\n\n"
#             "Respond strictly in JSON as specified."
#         )
#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             raise RuntimeError("No LLM provider configured")
#         try:
#             parsed = json.loads(out)
#         except Exception:
#             import re
#             m = re.search(r"(\{.*\})", out, re.S)
#             parsed = json.loads(m.group(1)) if m else {"intent": "other", "plan": [], "message": None, "notes": "no_json", "raw": out}
#         intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
#         plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
#         message = parsed.get("message")
#         notes = parsed.get("notes")
#         meta = parsed.get("meta")
#         ask = parsed.get("ask") or []
#         slots = parsed.get("slots") or {}
#         ready_to_buy = bool(parsed.get("ready_to_buy"))
#         next_stage = parsed.get("next_stage") or "qualify"
#         normalized = {
#             "intent": intent,
#             "plan": plan,
#             "message": message,
#             "notes": notes,
#             "meta": meta,
#             "ask": ask,
#             "slots": slots,
#             "ready_to_buy": ready_to_buy,
#             "next_stage": next_stage,
#             "raw": out
#         }
#         return NodeResult(normalized)


# class RecAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None

#         profile = (ctx.get("memory", {}) or {}).get("profile", {}) or {}
#         pref_filters = {}
#         if profile.get("size"):
#             pref_filters["size"] = profile["size"]
#         if profile.get("fit"):
#             pref_filters["fit"] = profile["fit"]
#         if profile.get("color_preference"):
#             pref_filters["color"] = profile["color_preference"]
#         if profile.get("budget"):
#             pref_filters["budget"] = profile["budget"]

#         # 1) Get recommendations (from meta or from user text)
#         if meta:
#             recs = await rec_agent.recommend_from_meta(meta, top_k=3)
#             if not recs:
#                 recs = await rec_agent.simple_keyword_recommend(
#                     meta.get("rec_query") or "",
#                     top_k=3,
#                     filters=pref_filters or meta.get("filters"),
#                 )
#         else:
#             user_text = ctx.get("incoming_text", "")
#             recs = await rec_agent.simple_keyword_recommend(
#                 user_text,
#                 top_k=3,
#                 filters=pref_filters,
#             )

#         recs = recs or []
#         for r in recs:
#             r["complements"] = rec_agent.complementary_for(r)

#         # 2) Try to deduce which product user is referring to by name / "this"
#         user_text_l = (ctx.get("incoming_text") or "").lower()
#         deduced = None
#         if user_text_l:
#             for r in recs:
#                 name = (r.get("name") or "").lower()
#                 if not name:
#                     continue
#                 # If name is directly mentioned or user uses "this/that" after seeing recs
#                 if name in user_text_l or "this" in user_text_l or "that" in user_text_l:
#                     deduced = r
#                     break

#         return NodeResult({"recs": recs, "deduced": deduced})


# # class InventoryAgentNode(Node):
# #     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
# #         nodouts = ctx.get("node_outputs", {}) or {}
# #         llm = nodouts.get("llm_intent") or {}

# #         meta = llm.get("meta") or {}
# #         selection = ctx.get("memory", {}).get("selection_state", {})
# #         product_id = (
# #             meta.get("sku")
# #             or meta.get("product_id")
# #             or selection.get("product_id")
# #         )


# #         if not product_id:
# #             return NodeResult({"available_stores": []})

# #         async with AsyncSessionLocal() as session:
# #             rows = await session.execute(
# #                 text("""
# #                     SELECT store_id, location, stock, reserved
# #                     FROM inventory
# #                     WHERE product_id = :pid
# #                 """),
# #                 {"pid": product_id}
# #             )
# #             rows = rows.fetchall()


# #         stores = []
# #         for r in rows:
# #             available = max((r.stock or 0) - (r.reserved or 0), 0)
# #             if available > 0:
# #                 stores.append({
# #                     "store_id": r.store_id,
# #                     "location": r.location,
# #                     "available_qty": available
# #                 })

# #         print(f"[INVENTORY] product={product_id} stores={stores}")

# #         return NodeResult({
# #             "product_id": product_id,
# #             "available_stores": stores
# #         })


# class InventoryAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm = nodouts.get("llm_intent") or {}
#         meta = llm.get("meta") or {}
        
#         # 1. Get User Location from Profile (Context Awareness)
#         profile = ctx.get("memory", {}).get("profile", {})
#         user_city = (profile.get("city") or "").lower() # e.g., "guntur"

#         selection = ctx.get("memory", {}).get("selection_state", {})
#         product_id = (
#             meta.get("sku")
#             or meta.get("product_id")
#             or selection.get("product_id")
#         )

#         if not product_id:
#             return NodeResult({"available_stores": []})

#         # 2. Query DB
#         async with AsyncSessionLocal() as session:
#             rows = await session.execute(
#                 text("SELECT store_id, location, stock, reserved FROM inventory WHERE product_id = :pid"),
#                 {"pid": product_id}
#             )
#             rows = rows.fetchall()

#         stores = []
#         local_store_found = False

#         # 3. Smart Filtering & Sorting
#         for r in rows:
#             available = max((r.stock or 0) - (r.reserved or 0), 0)
#             if available > 0:
#                 # Check if this store is in the user's city
#                 is_local = user_city in r.location.lower() if user_city else False
#                 if is_local: 
#                     local_store_found = True
                
#                 stores.append({
#                     "store_id": r.store_id,
#                     "location": r.location,
#                     "available_qty": available,
#                     "is_local": is_local
#                 })

#         # Sort: Local stores appear first in the list
#         stores.sort(key=lambda x: x['is_local'], reverse=True)

#         return NodeResult({
#             "product_id": product_id,
#             "available_stores": stores,
#             "user_city": user_city,
#             "local_store_found": local_store_found
#         })


#     # async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#     #     nodouts = ctx.get("node_outputs", {})
#     #     recs = nodouts.get("rec_agent", {}).get("recs", [])
#     #     invs = []
#     #     for p in recs:
#     #         pid = p.get("product_id")
#     #         inv = inventory_agent.check_stock_local(pid, self.store_id) or {}
#     #         stock = inv.get("stock", 0)
#     #         reserved = inv.get("reserved", 0)
#     #         available_qty = max(stock - reserved, 0)
#     #         invs.append({
#     #             "product_id": pid,
#     #             "stock": stock,
#     #             "reserved": reserved,
#     #             "available_qty": available_qty,
#     #             "is_available": available_qty > 0
#     #         })
#     #     return NodeResult({"inventory": invs})

# class CartAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_id = ctx.get("user_id", "anonymous")
#         sid = ctx.get("session_id", "user:anon:web")
#         channel = (sid.split(":")[-1] if ":" in sid else "web") or "web"

#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm = nodouts.get("llm_intent") or {}
#         meta = (llm.get("meta") or {}) if isinstance(llm, dict) else {}

#         rec_out = nodouts.get("rec_agent") or {}
#         recs = rec_out.get("recs", []) or []
#         deduced = rec_out.get("deduced")  # from RecAgentNode

#         qty = int(meta.get("qty", 1) or 1)

#         # ✅ HARD GATE:
#         # Only perform ANY cart mutation if meta.add is explicitly set.
#         # This avoids accidental adds on "yes" to loyalty, checkout, etc.
#         add_mode = meta.get("add")
#         if add_mode not in ("product_id", "first_rec"):
#             # No explicit add requested in this turn → NO-OP (silent)
#             return NodeResult({
#                 "success": False,
#                 "message": None  # don't show anything to user
#             })

#         # Helper to resolve a product_id from signals
#         def resolve_product_id() -> Optional[str]:
#             if meta.get("product_id"):
#                 return meta["product_id"]
#             if meta.get("sku"):
#                 return meta["sku"]

#             if isinstance(deduced, dict) and deduced.get("product_id"):
#                 return deduced["product_id"]

#             if recs:
#                 return recs[0].get("product_id")

#             return None

#         # =======================
#         # A) Explicit product_id
#         # =======================
#         if add_mode == "product_id":
#             pid = resolve_product_id()
#             if not pid:
#                 return NodeResult({"success": False, "message": "No item to add yet."})

#             summary = await cart_agent.add_specific_to_cart(
#                 user_id,
#                 channel,
#                 pid,
#                 qty=qty,
#             )
#             msg = f"Added to your cart. {summary['count']} item(s), subtotal ₹{summary['subtotal']}."
#             return NodeResult({"success": True, "cart": summary, "message": msg})

#         # =======================
#         # B) "first_rec" mode
#         # =======================
#         if add_mode == "first_rec":
#             if not recs:
#                 return NodeResult({"success": False, "message": "No recommendation to add yet."})

#             summary = await cart_agent.add_first_rec_to_cart(
#                 user_id,
#                 channel,
#                 recs[0],
#                 qty=qty,
#             )
#             msg = f"Added to your cart. {summary['count']} item(s), subtotal ₹{summary['subtotal']}."
#             return NodeResult({"success": True, "cart": summary, "message": msg})

#         # Fallback safety (should not hit)
#         return NodeResult({"success": False, "message": "No valid add mode."})


# class PaymentAgentNode(Node):
#     """
#     Handles:
#     - Loyalty points
#     - Loyalty redemption
#     - Price preview BEFORE payment
#     - Confirm payment flag
#     - Final QR creation only AFTER confirmation
#     - Stock validation & checkout (via /payment/confirm)
#     - Loyalty point awarding (handled in crud / checkout)
#     """

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         from backend.db import AsyncSessionLocal
#         from backend import crud as db_crud
#         from . import rec_agent, payment_agent

#         nodouts = ctx.get("node_outputs", {})
#         recs = (nodouts.get("rec_agent") or {}).get("recs", []) or []
#         llm_intent = nodouts.get("llm_intent") or {}

#         meta = llm_intent.get("meta") or {}
#         slots = llm_intent.get("slots") or {}
#         ready_to_buy = bool(llm_intent.get("ready_to_buy"))

#         user_id = ctx.get("user_id", "anonymous")

#         # ==========================================================
#         # 1️⃣ CHECK REQUIRED CHECKOUT SLOTS
#         # ==========================================================
#         required_for_checkout = ["size", "fit", "fulfillment"]
#         missing_required = [k for k in required_for_checkout if not slots.get(k)]

#         # Here we just react to state; gating of plan happens in run_master.
#         # Only block if we are truly in checkout flow
#         if not ready_to_buy:
#             return NodeResult({
#                 "success": False,
#                 "status": "idle",
#                 "message": None
#             })

#         if missing_required:
#             return NodeResult({
#                 "success": False,
#                 "status": "awaiting_checkout_details",
#                 "missing_slots": missing_required,
#                 "message": (
#                     "Before checkout, I need a few more details."
#                 )
#             })


#         # ==========================================================
#         # 2️⃣ DETERMINE PRODUCT (normalize SKU)
#         # ==========================================================
#         sku_raw = meta.get("sku")
#         prod: Optional[Dict[str, Any]] = None
#         product_id: Optional[str] = None

#         # A: Try SKU directly
#         if sku_raw:
#             prod = await rec_agent.get_product_by_sku(sku_raw)

#         # B: Normalize if needed: "P001-M-Black" → "P001"
#         if not prod and sku_raw and "-" in sku_raw:
#             base = sku_raw.split("-")[0]
#             prod = await rec_agent.get_product_by_sku(base)

#         # C: Fallback to first recommendation
#         if not prod and recs:
#             prod = recs[0]

#         if prod:
#             product_id = prod.get("product_id")

#         if not product_id:
#             return NodeResult({
#                 "success": False,
#                 "status": "selection_not_confirmed",
#                 "message": (
#                     "Should I proceed with the first recommendation, or would you like "
#                     "to pick a different product?"
#                 )
#             })

#         # ==========================================================
#         # 3️⃣ GET BASE PRICE
#         # ==========================================================
#         try:
#             base_price = float(prod.get("price") or 0.0)
#         except Exception:
#             base_price = 0.0

#         product_name = prod.get("name") or product_id

#         # ==========================================================
#         # 4️⃣ LOYALTY FETCH
#         # ==========================================================
#         async with AsyncSessionLocal() as session:
#             loyalty_info = await db_crud.get_user_loyalty(session, user_id)

#         current_points = loyalty_info.get("points", 0) or 0
#         loyalty_value = current_points * 0.5  # rupee equivalent

#         use_loyalty = slots.get("use_loyalty")
#         confirm_payment = slots.get("confirm_payment")

#         # ==========================================================
#         # 5️⃣ ASK ABOUT LOYALTY IF USER HAS POINTS & HAS NOT DECIDED YET
#         # ==========================================================
#         if current_points > 0 and use_loyalty is None:
#             return NodeResult({
#                 "success": False,
#                 "status": "needs_loyalty_decision",
#                 "message": (
#                     f"You have {current_points} loyalty points worth ₹{int(loyalty_value)}.\n"
#                     f"Would you like to redeem them for this {product_name} priced at ₹{int(base_price)}?"
#                 ),
#                 "meta": {
#                     "loyalty_points": current_points,
#                     "loyalty_value": loyalty_value,
#                     "product_id": product_id,
#                     "product_name": product_name,
#                     "base_price": base_price,
#                 }
#             })

#         # ==========================================================
#         # 6️⃣ CALCULATE PREVIEW AMOUNT (apply discount ONLY after user says yes)
#         # ==========================================================
#         loyalty_discount = 0.0
#         points_used = 0
#         final_amount = base_price

#         if current_points > 0 and use_loyalty is True:
#             # max discount = min(order price, points * 0.5)
#             loyalty_discount = min(base_price, current_points * 0.5)
#             points_used = int(loyalty_discount / 0.5)
#             final_amount = base_price - loyalty_discount
#         else:
#             final_amount = base_price

#         # ==========================================================
#         # 7️⃣ PREVIEW STAGE — USER MUST CONFIRM PAYMENT
#         # ==========================================================
#         if confirm_payment is None:
#             summary = (
#                 f"Here’s your order summary:\n"
#                 f"- Product: {product_name}\n"
#                 f"- Base Price: ₹{int(base_price)}\n"
#             )

#             if loyalty_discount > 0:
#                 summary += (
#                     f"- Loyalty Discount: ₹{int(loyalty_discount)} (using {points_used} points)\n"
#                 )

#             summary += f"- Final Payable: ₹{int(final_amount)}\n\n"
#             summary += "Should I proceed with payment?"

#             return NodeResult({
#                 "success": False,
#                 "status": "awaiting_payment_confirmation",
#                 "message": summary,
#                 "meta": {
#                     "product_id": product_id,
#                     "product_name": product_name,
#                     "base_price": base_price,
#                     "final_amount": final_amount,
#                     "points_used": points_used,
#                     "loyalty_discount": loyalty_discount,
#                 }
#             })

#         # ==========================================================
#         # 8️⃣ USER CONFIRMED → GENERATE PAYMENT INTENT & QR
#         # ==========================================================
#         if confirm_payment is True:
#             # Make payment intent
#             intent_id = "PINT-" + uuid.uuid4().hex[:8]
#             now = int(time.time())
#             expires_at = now + 120

#             qr_data = (
#                 f"upi://pay?pa=retailco@upi"
#                 f"&am={final_amount:.2f}"
#                 f"&tn=RetailCo%20Order%20{intent_id}"
#             )
#             # inside PaymentAgentNode, when confirm_payment is True — build intent_payload:
#             items_for_intent = [
#                                 {
#                                     "product_id": product_id,
#                                     "name": product_name,
#                                     "qty": int(meta.get("qty", 1) or 1),
#                                     "unit_price": float(prod.get("price") or 0.0),
#                                 }
#                                 ]


#             intent_payload = {
#                     "user_id": user_id,
#                     "sku": sku_raw or product_id,
#                     "product_id": product_id,
#                     "product_name": product_name,
#                     "items": items_for_intent,
#                     "qty": int(meta.get("qty", 1) or 1),
#                     "fulfillment": slots.get("fulfillment"),
#                     "base_price": base_price,
#                     "final_amount": float(final_amount),
#                     "amount": float(final_amount),   # compatibility
#                     "use_loyalty": bool(use_loyalty),
#                     "loyalty_discount": float(loyalty_discount),
#                     "points_used": int(points_used),
#                     "status": "pending",   # pending until confirmed
#                     "created_at": now,
#                     "expires_at": expires_at
#             }


#             await redis.set(f"payment_intent:{intent_id}", json.dumps(intent_payload), ex=180)

#             return NodeResult({
#                 "success": False,
#                 "status": "pending_payment",
#                 "mode": "qr",
#                 "payment_intent_id": intent_id,
#                 "qr_data": qr_data,
#                 "expires_at": expires_at,
#                 "amount": final_amount,
#                 "product_name": product_name,
#                 "message": (
#                     f"I've generated a UPI QR for ₹{int(final_amount)} for {product_name}. "
#                     f"Scan it and then tap 'I've paid'. This QR is valid for 2 minutes."
#                 )
#             })

#         # ==========================================================
#         # EDGE CASE: confirm_payment=False (user said no)
#         # ==========================================================
#         return NodeResult({
#             "success": False,
#             "status": "payment_cancelled",
#             "message": "Okay, I won't proceed. Let me know if you'd like to review other products."
#         })



# class OrderAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_id = ctx.get("user_id")
#         if not user_id:
#             return NodeResult({"orders": [], "error": "no_user"})
#         async with AsyncSessionLocal() as session:
#             try:
#                 rows = await db_crud.get_orders_for_user(session, user_id)
#                 orders = [{"order_id": r.order_id, "status": r.status, "items": r.items, "created_at": str(r.created_at)} for r in rows]
#                 return NodeResult({"orders": orders})
#             except Exception as e:
#                 return NodeResult({"orders": [], "error": str(e)})
            

        
# class FulfillmentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         from backend.db import AsyncSessionLocal
#         from backend import crud

#         nodouts = ctx.get("node_outputs", {})
#         llm = nodouts.get("llm_intent") or {}
#         slots = llm.get("slots") or {}

#         fulfillment = slots.get("fulfillment")
#         if fulfillment != "reserve_in_store":
#             return NodeResult({"mode": fulfillment})

#         user_id = ctx.get("user_id")
#         selection = ctx.get("memory", {}).get("selection_state", {})
#         product_id = selection.get("product_id")

#         inv = nodouts.get("inventory_agent") or {}
#         stores = inv.get("available_stores", [])

#         if not stores or not product_id:
#             return NodeResult({
#                 "success": False,
#                 "message": "Unable to reserve — product or store not available."
#             })

#         store_id = stores[0]["store_id"]

#         async with AsyncSessionLocal() as db:
#             reservation = await crud.create_reservation(
#                 db=db,
#                 user_id=user_id,
#                 product_id=product_id,
#                 store_id=store_id,
#                 qty=1,
#                 hold_minutes=45,
#             )

#         if not reservation:
#             return NodeResult({
#                 "success": False,
#                 "message": "Sorry — someone just reserved the last piece."
#             })

#         # 🔒 HARD STATE UPDATE (BACKEND OWNS THIS)
#         ctx["memory"]["stage"] = STAGES["CART"]
#         ctx["memory"]["reservation"] = reservation

#         return NodeResult({
#             "success": True,
#             "mode": "reserve_in_store",
#             "reservation": reservation,
#             "message": (
#                 f"✅ Reserved successfully at store {store_id}. "
#                 f"Please visit within 45 minutes and mention code {reservation['reservation_id']}."
#             )
#         })

            
# class PostPurchaseAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         # Very simple stub: just describes what we *could* do.
#         nodouts = ctx.get("node_outputs", {})
#         orders = (nodouts.get("order_agent") or {}).get("orders", [])
#         if not orders:
#             return NodeResult({
#                 "message": "I don't see any recent orders linked to your profile yet. Once you place an order, I can help you track it or start a return.",
#                 "actions": []
#             })
#         latest = orders[0]
#         return NodeResult({
#             "message": f"Your latest order {latest['order_id']} is currently {latest['status']}. I can help you with tracking, returns or exchanges.",
#             "actions": ["track", "return", "exchange"]
#         })
        






# def _canonicalize_session_id(raw_sid: str, user_id: Optional[str], default_channel: str = "web") -> str:
#     channel = default_channel
#     if ":" in (raw_sid or ""):
#         channel = (raw_sid.split(":")[0] or default_channel).lower()
#     if user_id:
#         return f"user:{user_id}:{channel}"
#     return raw_sid
# def get_missing_attributes(product: Dict[str, Any], selected_attrs: Dict[str, Any]):
#     missing = []
#     attributes = product.get("attributes", {}) or {}

#     for attr_name, attr_def in attributes.items():
#         if not isinstance(attr_def, dict):
#             continue

#         required = attr_def.get("required", False)
#         options = attr_def.get("options", [])

#         if required and not selected_attrs.get(attr_name):
#             missing.append({
#                 "name": attr_name,
#                 "options": options
#             })

#     return missing


# def render_product_details(product: dict) -> dict:
#     return {
#         "product_id": product.get("product_id"),
#         "name": product.get("name"),
#         "price": product.get("price"),
#         "category": product.get("category"),
#         "description": product.get("description"),
#         "attributes": product.get("attributes", {}),
#         "images": product.get("images", []),
#         "complements": product.get("complements", [])
#     }


# async def run_master(session_id: str, incoming_text: str, user_meta: Optional[Dict[str, Any]] = None):
#     # RENAME ARGUMENT 'text' -> 'incoming_text' TO AVOID SHADOWING SQLALCHEMY
    
#     user_id = (user_meta or {}).get("user_id")
#     canonical_sid = _canonicalize_session_id(session_id, user_id=user_id, default_channel="web")
    
#     # 1. Session Merging & Loading
#     if canonical_sid != session_id:
#         try:
#             await merge_sessions(session_id, canonical_sid, keep_last=10)
#         except Exception:
#             pass
#         session_id = canonical_sid
    
#     try:
#         active_sid = await get_active_session_for_user(user_id) if user_id else None
#         if active_sid and active_sid != session_id:
#             await merge_sessions(active_sid, session_id, keep_last=10)
#     except Exception:
#         pass

#     session = await load_session(session_id)
#     profile = await load_user_profile(user_id) 
    
#     # ================================
#     # 🔒 SESSION MEMORY INITIALIZATION
#     # ================================
#     session.setdefault("memory", {})
#     session["memory"].setdefault("stage", STAGES["RECOMMEND"])
#     session["memory"].setdefault("selection_state", {
#         "product_id": None,
#         "selected_attributes": {},
#     })
#     session["memory"].setdefault("reservation", {
#         "store_id": None,
#         "date": None,
#         "time": None,
#     })

#     # ================================
#     # BACKEND RESERVE INPUT PARSER
#     # ================================
#     if session["memory"]["stage"] == STAGES["RESERVE"]:
#         reservation = session["memory"]["reservation"]
#         # Use incoming_text here
#         user_text = (incoming_text or "").lower()
#         import re

#         # ---- Store ID (S1, s1, store s1) ----
#         if not reservation.get("store_id"):
#             m = re.search(r"\b(s\d+)\b", user_text)
#             if m:
#                 reservation["store_id"] = m.group(1).upper()

#         # ---- Date parsing (simple) ----
#         if not reservation.get("date"):
#             if "today" in user_text:
#                 reservation["date"] = "today"
#             elif "tomorrow" in user_text:
#                 reservation["date"] = "tomorrow"
#             else:
#                 m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", user_text)
#                 if m:
#                     reservation["date"] = m.group(1)

#         # ---- Time parsing ----
#         if not reservation.get("time"):
#             m = re.search(r"\b(\d{1,2})(?:\s*:\s*(\d{2}))?\s*(am|pm)?\b", user_text)
#             if m:
#                 hour = m.group(1)
#                 minute = m.group(2) or "00"
#                 meridian = m.group(3) or ""
#                 reservation["time"] = f"{hour}:{minute} {meridian}".strip()

#         session["memory"]["reservation"] = reservation
#         print("[DEBUG][PARSE] reservation now =", reservation)

#     # ================================
#     # GRAPH SETUP
#     # ================================
#     ctx = {
#         "session_id": session_id,
#         "user_id": user_id,
#         "incoming_text": incoming_text, # Updated here
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     cart_node = CartAgentNode("cart_agent")
#     inventory_node = InventoryAgentNode("inventory_agent")
#     pay_node = PaymentAgentNode("payment_agent")
#     order_node = OrderAgentNode("order_agent")
#     loyalty_node = LoyaltyAgentNode("loyalty_agent")
#     fulfill_node = FulfillmentAgentNode("fulfillment_agent")
#     postpurchase_node = PostPurchaseAgentNode("postpurchase_agent")

#     for n in [llm_node, rec_node,  inventory_node, cart_node, pay_node, order_node, loyalty_node, fulfill_node, postpurchase_node]:
#         g.add_node(n)

#     # ================================
#     # RUN LLM INTENT
#     # ================================
#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []
#     slots = (intent_out.get("slots") or {}) if isinstance(intent_out, dict) else {}
#     ready_to_buy = bool(intent_out.get("ready_to_buy"))
#     next_stage = intent_out.get("next_stage") or "qualify"
#     meta = intent_out.get("meta") or {}

#     user_text_lower = (incoming_text or "").lower() # Updated here

#     # ================================
#     # 🩹 FIX 2: GLOBAL RESERVE TRANSITION (Pre-Execution)
#     # Allows "reserve" command to work from ANY stage
#     # ================================
#     if "reserve" in user_text_lower and session["memory"]["stage"] != STAGES["RESERVE"]:
#         # Only if product is selected
#         if session["memory"]["selection_state"].get("product_id") or meta.get("sku"):
#              print("[DEBUG][STATE] Global override -> forcing stage RESERVE")
#              session["memory"]["stage"] = STAGES["RESERVE"]
#              if meta.get("sku"):
#                  session["memory"]["selection_state"]["product_id"] = meta["sku"]
             
#              # Immediately save and ask for store
#              await save_session(session_id, session)
#              return {
#                 "session_id": session_id,
#                 "results": {
#                     "message": "Sure! Which store would you like to reserve this at?"
#                 },
#                 "next_stage": STAGES["RESERVE"],
#             }

#     # ================================
#     # 🔒 HARD RESERVE FLOW EXECUTION
#     # ================================
#     if session["memory"]["stage"] == STAGES["RESERVE"]:
#         reservation = session["memory"]["reservation"]
#         selection = session["memory"]["selection_state"]

#         # ---- guards ----
#         if not user_id:
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Please login to reserve items."},
#                 "next_stage": STAGES["RECOMMEND"],
#             }

#         if not selection.get("product_id"):
#             session["memory"]["stage"] = STAGES["RECOMMEND"]
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Please select a product again."},
#                 "next_stage": STAGES["RECOMMEND"],
#             }

#         # ---- ask steps ----
#         if not reservation.get("store_id"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Which store would you like to reserve this at?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         if not reservation.get("date"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "What date would you like to visit the store?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         if not reservation.get("time"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "What time should I reserve it for?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         # ================================
#         # 🔒 INVENTORY CHECK + INSERT (SAME TX)
#         # ================================
#         async with AsyncSessionLocal() as db:
#             # THIS was causing the crash because 'text' was shadowed. 
#             # Now 'text' refers correctly to sqlalchemy.text
#             result = await db.execute(
#                 text("""
#                     SELECT stock, reserved
#                     FROM inventory
#                     WHERE product_id = :pid AND store_id = :sid
#                     FOR UPDATE
#                 """),
#                 {
#                     "pid": selection["product_id"],
#                     "sid": reservation["store_id"],
#                 }
#             )
#             row = result.fetchone()

#             if not row or (row.stock - row.reserved) <= 0:
#                 session["memory"]["stage"] = STAGES["AVAILABILITY"]
#                 await save_session(session_id, session)
#                 return {
#                     "session_id": session_id,
#                     "results": {"message": "❌ Sorry, this item just went out of stock."},
#                     "next_stage": STAGES["AVAILABILITY"],
#                 }

#             await db_crud.create_reservation(
#                 db=db,
#                 user_id=user_id,
#                 product_id=selection["product_id"],
#                 store_id=reservation["store_id"],
#                 date=reservation["date"],
#                 time=reservation["time"],
#             )

#         # ================================
#         # 🔒 LOCK STATE AFTER SUCCESS
#         # ================================
#         session["memory"]["selection_state"]["reserved"] = True
#         session["memory"]["stage"] = STAGES["CART"]
#         session["memory"]["reservation"] = {
#             "store_id": None,
#             "date": None,
#             "time": None,
#         }

#         await save_session(session_id, session)

#         return {
#             "session_id": session_id,
#             "results": {
#                 "message": (
#                     f"✅ Reserved at {reservation['store_id']} on "
#                     f"{reservation['date']} at {reservation['time']}."
#                 )
#             },
#             "next_stage": STAGES["CART"],
#         }

#     # ======================================================
#     # STEP 3: HARD PLAN OVERRIDE — DO NOT TRUST LLM PLAN
#     # ======================================================

#     stage = session["memory"].get("stage", STAGES["RECOMMEND"])

#     if stage == STAGES["RECOMMEND"]:
#         plan = ["rec_agent"]

#     elif stage == STAGES["PRODUCT_DETAILS"]:
#         # 🩹 FIX 1: Allow inventory check if user explicitly asks
#         if "inventory_agent" in plan or meta.get("check_availability") or any(x in user_text_lower for x in ["stock", "availabl", "reserve"]):
#              plan = ["inventory_agent"]
#         else:
#              plan = []  # no agent, just show details

#     elif stage == STAGES["AVAILABILITY"]:
#         plan = ["inventory_agent"]

#     elif stage == STAGES["RESERVE"]:
#         plan = [] 

#     elif stage == STAGES["CART"]:
#         plan = ["cart_agent"]

#     elif stage == STAGES["CHECKOUT"]:
#         plan = ["payment_agent"]

#     elif stage == STAGES["PAYMENT"]:
#         plan = []

#     elif stage == STAGES["ORDER_CONFIRMED"]:
#         plan = []
        
#     # 🚫 FIX 3 — NEVER re-run inventory after reservation
#     if session["memory"]["selection_state"].get("reserved") is True:
#         plan = [p for p in plan if p != "inventory_agent"]

#     # 🔒 HARD BLOCK checkout-related agents unless explicitly in CHECKOUT or PAYMENT
#     if session["memory"]["stage"] not in (STAGES["CHECKOUT"], STAGES["PAYMENT"]):
#         plan = [
#             p for p in plan
#             if p not in ("payment_agent", "loyalty_agent", "order_agent")
#         ]

#     if not plan and intent == "recommend":
#         plan = ["rec_agent"]
#     elif not plan and intent == "buy":
#         plan = ["rec_agent"]
#     elif not plan and intent == "postpurchase":
#         plan = ["order_agent", "postpurchase_agent"]

#     # Only block payment_agent if the user is NOT ready_to_buy.
#     if "payment_agent" in plan and not ready_to_buy:
#         plan = [p for p in plan if p != "payment_agent"]
        
#     selection_state = session["memory"].get("selection_state", {})
    
#     # ================================
#     # STATE TRANSITION: RECOMMEND → PRODUCT_DETAILS
#     # ================================
#     if meta.get("confirm_selection") and meta.get("sku"):
#         session["memory"]["selection_state"]["product_id"] = meta["sku"]
#         session["memory"]["stage"] = STAGES["PRODUCT_DETAILS"]
        
#     # ================================
#     # STATE TRANSITION: PRODUCT_DETAILS → AVAILABILITY
#     # ================================
#     if session["memory"]["stage"] == STAGES["PRODUCT_DETAILS"]:
#         if any(x in user_text_lower for x in ["check", "availability", "stock", "yes"]):
#             session["memory"]["stage"] = STAGES["AVAILABILITY"]
    
#     # 🚫 Block checkout if product is out of stock
#     if selection_state.get("out_of_stock") is True:
#         plan = [p for p in plan if p != "payment_agent"]
#         ready_to_buy = False

#     # 🔒 FORCE INVENTORY ONLY WHEN USER EXPLICITLY ASKS
#     if (
#         meta.get("check_availability") is True
#         and (meta.get("sku") or selection_state.get("product_id"))
#     ):
#         selection_state["product_id"] = meta.get("sku") or selection_state.get("product_id")
#         selection_state["selected_attributes"] = {}
#         session["memory"]["selection_state"] = selection_state

#         plan = ["inventory_agent"]
#         next_stage = "availability"
#         ready_to_buy = False

#     # ================================
#     # EXECUTE PLAN
#     # ================================
#     from difflib import get_close_matches
#     validated_plan = []
#     missing_nodes = []
#     for nid in plan:
#         if nid in g.nodes:
#             validated_plan.append(nid)
#             continue
#         matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
#         if matches:
#             validated_plan.append(matches[0])
#         else:
#             lname = nid.lower()
#             mapped = None
#             if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
#                 mapped = "rec_agent"
#             elif any(tok in lname for tok in ("inventory","stock","availability")):
#                 mapped = "inventory_agent"
#             elif any(tok in lname for tok in ("cart","basket","add to cart","add2cart","add")):
#                 mapped = "cart_agent"
#             elif any(tok in lname for tok in ("pay","payment","checkout","order")):
#                 mapped = "payment_agent"
#             if mapped and mapped in g.nodes:
#                 validated_plan.append(mapped)
#             else:
#                 missing_nodes.append(nid)

#     for node_id in validated_plan:
#         res = await g.nodes[node_id].run(ctx)
#         ctx["node_outputs"][node_id] = res.output
#         try:
#             print("[DEBUG] node_outputs keys:", list(ctx["node_outputs"].keys()))
#             # Debug logging...
#         except Exception:
#             pass
        
#     # ================================
#     # PROFILE & SLOTS UPDATES
#     # ================================
#     if isinstance(meta, dict):
#         profile_patch = meta.get("profile") or {}
#         if profile_patch and user_id:
#             await save_user_profile(user_id, profile_patch)
#             session["memory"].setdefault("profile", {}).update(profile_patch)
    
#     slot_patch = {
#         k: v for k, v in (slots or {}).items()
#         if v not in (None, "", [])
#         and not (
#             next_stage in ("recommend", "validate", "availability")
#             and k in ("size", "fit", "color_preference")
#         )
#     }
#     if slot_patch and user_id:
#         await save_user_profile(user_id, slot_patch)
#         session["memory"].setdefault("profile", {}).update(slot_patch)

#     # ================================
#     # CAPTURE PRODUCT-SPECIFIC ATTRIBUTES
#     # ================================
#     selection_state = session["memory"].get("selection_state", {})
    
#     # ♻️ Clear out-of-stock flag if user selects a new product
#     if meta.get("sku") and meta.get("sku") != selection_state.get("product_id"):
#         selection_state.pop("out_of_stock", None)
#         selection_state["product_id"] = meta.get("sku")
#         session["memory"]["selection_state"] = selection_state

#     active_pid = selection_state.get("product_id")

#     if active_pid:
#         selected_attrs = selection_state.setdefault("selected_attributes", {})
#         for k, v in (slots or {}).items():
#             if v not in (None, "", []):
#                 selected_attrs[k] = v
#         session["memory"]["selection_state"] = selection_state

#     # ================================
#     # BUILD FINAL RESPONSE
#     # ================================
#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     recs = []
#     active_product = None

#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         selection_state = session["memory"].get("selection_state", {})
#         active_pid = selection_state.get("product_id")

#     active_product = None
#     for p in recs:
#         if p.get("product_id") == active_pid:
#             active_product = p
#             break

#     # 🔁 FALLBACK TO DB IF NOT IN CURRENT RECS
#     if not active_product and active_pid:
#         active_product = await rec_agent.get_product_by_sku(active_pid)

#     # ================================
#     # STEP B: SHOW PRODUCT DETAILS (READ-ONLY MODE)
#     # ================================
#     meta = intent_out.get("meta") or {}

#     if active_product and meta.get("show_product_details") is True:
#         final["results"]["product_details"] = {
#             "product_id": active_product.get("product_id"),
#             "name": active_product.get("name"),
#             "price": float(active_product.get("price", 0)),
#             "category": active_product.get("category"),
#             "description": active_product.get("description"),
#             "attributes": active_product.get("attributes", {}),
#             "images": active_product.get("images", []),
#             "complements": active_product.get("complements", []),
#         }
#         final["results"]["message"] = (
#             f"{active_product.get('name')} is priced at ₹{int(active_product.get('price', 0))}. "
#             f"{active_product.get('description') or ''}"
#         )
#         final["results"]["ask"] = [
#             "Would you like me to check availability in nearby stores?"
#         ]
#         await save_session(session_id, session)
#         return final
    
#     # ================================
#     # HANDLE INVENTORY OUTPUT
#     # ================================
#     if "inventory_agent" in outs:
#         inv = outs["inventory_agent"]
#         stores = inv.get("available_stores", [])
        
#         # 🚫 HARD STOP: out of stock
#         if not stores:
#             final["results"]["out_of_stock"] = True
#             final["results"]["message"] = (
#                 "I'm sorry, I checked everywhere but this item is currently out of stock. "
#                 "Shall I notify you when it returns?"
#             )
#             session["memory"]["selection_state"]["out_of_stock"] = True
#             await save_session(session_id, session)
#             return final

#         # Availability response
#         final["results"]["stores"] = stores
#         final["results"]["ask"] = [
#             "Would you like to add this to cart, reserve it in store, or ship it?"
#         ]
#         final["results"]["force_action"] = "fulfillment_choice"
#         final["next_stage"] = "availability"
#         final["ready_to_buy"] = False

#         # ✅ STATE TRANSITION: AVAILABILITY → CART 
#         if any(x in user_text_lower for x in ["add", "cart"]):
#             session["memory"]["stage"] = STAGES["CART"]

#         session["memory"]["selection_state"]["inventory_checked"] = True
#         await save_session(session_id, session)
#         return final

#     # ================================
#     # HANDLE CART AGENT
#     # ================================
#     if "cart_agent" in outs:
#         # CHECKOUT FLOW (LOCKED)
#         if session["memory"]["stage"] == STAGES["CHECKOUT"]:
#             cart = outs.get("cart_agent", {}).get("cart")
#             if not cart or not cart.get("items"):
#                 final["results"]["message"] = "Your cart is empty. Would you like me to add something first?"
#                 await save_session(session_id, session)
#                 return final

#             # Fetch loyalty info
#             async with AsyncSessionLocal() as db:
#                 loyalty = await db_crud.get_user_loyalty(db, user_id)

#             final["results"]["cart"] = cart
#             final["results"]["loyalty"] = loyalty
#             final["results"]["message"] = (
#                 f"Here’s your cart summary:\n"
#                 f"- Items: {len(cart['items'])}\n"
#                 f"- Subtotal: ₹{int(cart['subtotal'])}\n\n"
#                 f"You have {loyalty['points']} loyalty points.\n"
#                 f"Would you like to redeem them for this order?"
#             )
#             await save_session(session_id, session)
#             return final

#     # ================================
#     # STATE TRANSITION: CART → CHECKOUT
#     # ================================
#     if "checkout" in user_text_lower:
#         session["memory"]["stage"] = STAGES["CHECKOUT"]
#         if "cart_agent" in outs:
#             final["results"]["cart"] = outs["cart_agent"].get("cart")
#             ca_msg = outs["cart_agent"].get("message")
#             if ca_msg:
#                 final["results"]["cart_message"] = ca_msg

#     # ================================
#     # COLLECT OTHER AGENT OUTPUTS
#     # ================================
#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]
#     if "order_agent" in outs:
#         final["results"]["orders"] = outs["order_agent"].get("orders", [])
    
#     items = []
#     for p in recs:
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#             "complements": p.get("complements", [])
#         })
#     if items:
#         final["results"]["items"] = items
        
#     if "loyalty_agent" in outs:
#         final["results"]["loyalty"] = outs["loyalty_agent"]
#     if "fulfillment_agent" in outs:
#         final["results"]["fulfillment"] = outs["fulfillment_agent"]
#     if "postpurchase_agent" in outs:
#         final["results"]["postpurchase"] = outs["postpurchase_agent"]

#     # ================================
#     # MESSAGE CONSTRUCTION HELPERS
#     # ================================
#     def _merge_msg_and_questions(msg: Optional[str], qs: List[str]) -> str:
#         base = (msg or "").strip()
#         if not qs:
#             return base or "How can I help you find the right piece today?"
        
#         def _norm(s: str) -> str:
#             return s.strip().rstrip(" ?!.").lower()

#         base_norm = _norm(base) if base else ""
#         unique_q = None
#         for q in qs:
#             q = (q or "").strip()
#             if not q: continue
#             if base and _norm(q) in base_norm: continue
#             unique_q = q
#             break

#         if not unique_q:
#             return base or "How can I help you find the right piece today?"
#         return (base + " " + unique_q) if base else unique_q

#     def _normalize_order_result(order_obj):
#         if not isinstance(order_obj, dict):
#             return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
#         status = order_obj.get("status")
#         if status is None and "success" in order_obj:
#             status = "success" if bool(order_obj.get("success")) else "error"
#         order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
#         return {
#             "status": status,
#             "success": bool(order_obj.get("success") or (status == "success")),
#             "order_id": order_id,
#             "message": order_obj.get("message"),
#             "error": order_obj.get("error"),
#             "raw": order_obj,
#         }

#     order = final["results"].get("order", {})
#     order_norm = _normalize_order_result(order)
#     status = order.get("status") if isinstance(order, dict) else None

#     # ================================
#     # FINAL MESSAGE DECISION LOGIC
#     # ================================
#     if order:
#         # 1) Payment / Pre-Checkout States
#         if status in ("needs_loyalty_decision", "awaiting_payment_confirmation", "not_ready", "payment_cancelled"):
#             final["results"]["message"] = order.get("message") or final["results"].get("message")
        
#         # 2) Pending QR
#         elif status in ("pending", "pending_payment"):
#             final_msg = order.get("message") or "I've generated a payment QR for you. Please scan it and then confirm."
#             final["results"]["message"] = final_msg
        
#         # 3) Final Success / Error
#         elif order_norm["success"] or order_norm["status"] in ("success", "error"):
#             err = order_norm.get("error") or (order.get("error"))
#             agent_msg = order.get("message") or order.get("details")
#             if agent_msg:
#                 final_msg = agent_msg
#             elif err == "out_of_stock":
#                 sku = (order.get("meta") or {}).get("sku")
#                 final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
#             else:
#                 final_msg = f"Order failed: {err or 'unknown_error'}."
#             final["results"]["message"] = final_msg
        
#         # 4) Fallback to LLM message
#         else:
#             llm_message = intent_out.get("message")
#             llm_ask = intent_out.get("ask") or []
#             if llm_message or llm_ask:
#                 final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
#             else:
#                  final["results"]["message"] = "Here are the results."
#     else:
#         # No order object -> Normal LLM message
#         llm_message = intent_out.get("message")
#         llm_ask = intent_out.get("ask") or []
        
#         if llm_message or llm_ask:
#             final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
#         else:
#             # Fallback based on context
#             if intent == "recommend" and items:
#                 final["results"]["message"] = f"I found {len(items)} items — here are the top matches. What occasion are you shopping for?"
#             elif intent == "other":
#                 mem = session.get("memory", {})
#                 if "name" in mem and "what is my name" in (incoming_text or "").lower():
#                     final["results"]["message"] = f"Your name is {mem['name']}."
#                 else:
#                     final["results"]["message"] = "Hello! I can help you find and buy products. What occasion are you shopping for?"
#             else:
#                 final["results"]["message"] = "Here are the results. Would you like casual or office wear?"

#     try:
#         print(f"[MASTER] final message -> {final['results'].get('message')}")
#     except Exception:
#         pass

#     # ================================
#     # SAVE HISTORY & RETURN
#     # ================================
#     session.setdefault("history", []).append({
#         "incoming": incoming_text,
#         "intent": intent,
#         "results": final["results"],
#         "slots": slots,
#         "next_stage": next_stage
#     })
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(incoming_text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
    
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)
#     if user_id:
#         await set_active_session_for_user(user_id, session_id)
        
#     final["llm_notes"] = intent_out.get("notes")
#     final["slots"] = slots
    
#     if slots.get("confirm_payment") is True:
#         session["memory"]["stage"] = STAGES["PAYMENT"]
    
#     final["next_stage"] = session["memory"]["stage"]
#     final["ready_to_buy"] = ready_to_buy
#     return final







# backend/agents/master_graph.py
########################## human like ###########################
import os
import json
import uuid
import time
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
load_dotenv()
import traceback

from redis.asyncio import Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis = Redis.from_url(REDIS_URL, decode_responses=True)

import httpx
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

from . import rec_agent, inventory_agent, payment_agent, cart_agent

from backend.agents import postpurchase_agent


from sqlalchemy import text




from backend.db import AsyncSessionLocal
from backend import crud as db_crud

from backend.agents.base import Node, NodeResult

from google import genai
from google.genai import types





GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_GEMINI = os.getenv("USE_GEMINI", "false").lower() in ("1", "true", "yes")

gemini_client = None
if USE_GEMINI and GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)



class AgentGraph:
    def __init__(self, graph_id: Optional[str] = None):
        self.nodes: Dict[str, Node] = {}
        self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

    def add_node(self, node: Node):
        self.nodes[node.id] = node
        
class LoyaltyAgentNode(Node):
    def __init__(self, id: str = "loyalty_agent"):
        super().__init__(id)

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        user_id = ctx.get("user_id")

        # If there is no logged-in user, return zeroed-out loyalty info
        if not user_id:
            return NodeResult({
                "points": 0,
                "points_value": 0.0,
                "tier": "Bronze",
                "total_spend": 0.0,
                "promo": None,
            })

        # Use your real DB-backed helper from crud.py
        async with AsyncSessionLocal() as session:
            info = await db_crud.get_user_loyalty(session, user_id)

        points = info.get("points", 0)
        total_spend = float(info.get("total_spend", 0.0) or 0.0)
        tier = info.get("tier") or "Bronze"
        points_value = points * 0.5  # ₹ value per point

        # Optional promo stub – you can customize or remove this
        promo = {
            "code": "WEDDING10",
            "description": "10% off on wedding outfits",
            "discount_pct": 10,
        }

        return NodeResult({
            "points": points,
            "points_value": points_value,
            "tier": tier,
            "total_spend": total_spend,
            "promo": promo,
        })



SESSION_PREFIX = "session:"
USER_ACTIVE_KEY_PREFIX = "user_active_session:"
USER_PROFILE_PREFIX = "user_profile:"


# ===============================
# HARD FLOW STATES (SOURCE OF TRUTH)
# ===============================
STAGES = {
    "RECOMMEND": "recommend",
    "PRODUCT_DETAILS": "product_details",
    "AVAILABILITY": "availability",
    "RESERVE": "reserve_in_store",
    "CART": "cart",
    "CHECKOUT": "checkout",
    "PAYMENT": "payment",
    "ORDER_CONFIRMED": "order_confirmed"
}



async def load_session(session_id: str) -> Dict[str, Any]:
    key = SESSION_PREFIX + session_id
    raw = await redis.get(key)
    if not raw:
        return {"session_id": session_id, "memory": {}, "history": []}
    try:
        return json.loads(raw)
    except Exception:
        return {"session_id": session_id, "memory": {}, "history": []}


async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24 * 7):
    key = SESSION_PREFIX + session_id
    await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


async def get_active_session_for_user(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    return await redis.get(USER_ACTIVE_KEY_PREFIX + user_id)


async def set_active_session_for_user(user_id: Optional[str], session_id: str, ttl_seconds: int = 60 * 60 * 24 * 7):
    if not user_id:
        return
    await redis.set(USER_ACTIVE_KEY_PREFIX + user_id, session_id, ex=ttl_seconds)


async def merge_sessions(from_sid: Optional[str], into_sid: Optional[str], keep_last: int = 10):
    if not from_sid or not into_sid or from_sid == into_sid:
        return
    old = await load_session(from_sid)
    new = await load_session(into_sid)
    merged = {
        "session_id": into_sid,
        "memory": {**(old.get("memory") or {}), **(new.get("memory") or {})},
        "history": ((old.get("history") or []) + (new.get("history") or []))[-keep_last:],
        "last_updated": __import__("time").time()
    }
    await save_session(into_sid, merged)
    



async def load_user_profile(user_id: Optional[str]) -> Dict[str, Any]:
    if not user_id:
        return {}
    raw = await redis.get(USER_PROFILE_PREFIX + user_id)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


async def save_user_profile(user_id: Optional[str], patch: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24 * 90):
    if not user_id or not isinstance(patch, dict):
        return
    key = USER_PROFILE_PREFIX + user_id
    cur = await load_user_profile(user_id)
    cur.update({k: v for k, v in patch.items() if v is not None})
    await redis.set(key, json.dumps(cur), ex=ttl_seconds)

# backend/agents/master_graph.py

# ... existing imports ...

async def clear_user_memory(user_id: str):
    """
    Clears:
    1. The active session pointer.
    2. The actual session data (Memory, Stage).
    3. The cached User Profile.
    Does NOT touch the SQL database (Carts/Reservations remain safe).
    """
    if not user_id:
        return

    # 1. Get the current active session ID so we can delete the actual session data
    active_sid = await redis.get(USER_ACTIVE_KEY_PREFIX + user_id)

    keys_to_delete = []
    
    # Active Session Pointer
    keys_to_delete.append(USER_ACTIVE_KEY_PREFIX + user_id)
    
    # Cached User Profile
    keys_to_delete.append(USER_PROFILE_PREFIX + user_id)

    # The Session Data itself
    if active_sid:
        keys_to_delete.append(SESSION_PREFIX + active_sid)
    
    # Also clean canonical web session to be safe
    keys_to_delete.append(SESSION_PREFIX + f"user:{user_id}:web")

    if keys_to_delete:
        await redis.delete(*keys_to_delete)
        print(f"[MEMORY] Cleared Redis keys for {user_id}: {keys_to_delete}")

class LLMAgentNode(Node):
    def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
        super().__init__(id)
        available_agents = [
    "rec_agent",
    "inventory_agent",
    "cart_agent",
    "payment_agent",
    "order_agent",
    "loyalty_agent",
    "fulfillment_agent",
    "postpurchase_agent",
]
        agents_text = ", ".join(available_agents)
        
       
#         self.system_prompt = system_prompt or """
# You are "Aura," a Top-Tier Retail Sales Associate for a premium fashion brand. 
# RESPOND IN JSON ONLY.

# AVAILABLE_AGENTS: rec_agent, inventory_agent, cart_agent, payment_agent, order_agent, loyalty_agent, fulfillment_agent, postpurchase_agent

# ──────────────────────────────────────────────────────────────
# 🧠 SALES PSYCHOLOGY & BEHAVIOR (CRITICAL)
# ──────────────────────────────────────────────────────────────
# 1. NEVER be a "Vending Machine". Do not just dump product lists immediately unless the user is very specific.
# 2. THE CONSULTATIVE LOOP:
#    - If user says "Show me shirts": 
#      ❌ Bad: "Here are 5 shirts."
#      ✅ Good: "I'd love to help! Are you looking for something formal for work, or a casual weekend vibe?"
#    - Ask ONE clarifying question at a time (Occasion, Fit, Fabric, or Color).

# 3. THE UPSELL (Cross-Selling):
#    - If the user selects a Product (e.g., a Suit), suggest a complement (e.g., a Tie or Pocket Square) before checkout.
#    - Use phrases like: "That jacket is a great choice. It pairs perfectly with these chinos..."

# 4. CONTEXT AWARENESS:
#    - Check UserProfile.city. If they are in "Guntur", prioritize mentions of the Guntur store.
#    - If UserProfile.loyalty_points > 1000, mention they have points to redeem.

# ──────────────────────────────────────────────────────────────
# MEMORY & TRUTH SOURCE
# ──────────────────────────────────────────────────────────────
# Use SessionMemory.profile + ConversationHistory as the SINGLE source of truth.
# If information is already present in memory (e.g., size, city), DO NOT ask for it again.

# ──────────────────────────────────────────────────────────────
# PRODUCT SELECTION & IDENTIFICATION RULES
# ──────────────────────────────────────────────────────────────
# User signals for selection: "this looks good", "give me details", "I want this", "add this".

# When product intent is detected, you MUST output:
# "meta": {
#   "sku": "<product_id>",
#   "confirm_selection": true
# }

# Set intent = "buy" but ready_to_buy = false initially.

# ──────────────────────────────────────────────────────────────
# PRODUCT ATTRIBUTE RESOLUTION
# ──────────────────────────────────────────────────────────────
# When a product is selected, check its `attributes` (size/color).
# - Ask ONLY for missing REQUIRED attributes.
# - Present options EXACTLY as provided in the product data.
# - Once attributes are resolved, transition to Fulfillment.

# ──────────────────────────────────────────────────────────────
# FULFILLMENT & INVENTORY
# ──────────────────────────────────────────────────────────────
# After attributes are resolved, ask:
# “Would you like to reserve it in store to try, or **add it to your cart**?”
# (Do NOT ask to 'ship' directly. Shipping happens inside checkout).

# ──────────────────────────────────────────────────────────────
# CART ACTION RULES
# ──────────────────────────────────────────────────────────────
# Trigger cart actions ONLY on explicit phrases like "add to cart" or "buy now".
# - Include "cart_agent" in plan.
# - Set meta.add = "product_id".

# ──────────────────────────────────────────────────────────────
# CHECKOUT & LOYALTY RULES
# ──────────────────────────────────────────────────────────────
# 1. TRIGGER: When user says "Checkout", "Buy Now", or "Ship to address":
#    - Set intent = "buy"
#    - Set ready_to_buy = true
#    - Include "payment_agent" in plan.

# 2. LOYALTY DECISION:
#    - If user answers the loyalty question (e.g., "Yes use points", "No"):
#      - Set slots.use_loyalty = true OR false.
#      - Set ready_to_buy = true (to re-trigger payment agent).

# 3. QR GENERATION:
#    - Do NOT ask for final confirmation after loyalty is decided. 
#    - The Payment Agent will generate the QR code immediately. 
#    - Just let the agent run.

# ──────────────────────────────────────────────────────────────
# PRODUCT DETAIL INTENT
# ──────────────────────────────────────────────────────────────
# If user asks to see details/features of a selected product:
# - Set meta.show_product_details = true.
# - Do NOT initiate checkout yet.

# ──────────────────────────────────────────────────────────────
# STRICT JSON OUTPUT SCHEMA
# ──────────────────────────────────────────────────────────────
# {
#   "intent": "recommend" | "buy" | "postpurchase" | "other" | "profile" | "qualify",
#   "plan": ["string"],
#   "message": "string",
#   "ask": ["string"],

#   "slots": {
#     "occasion": null | "string",
#     "size": null | "string",
#     "fit": null | "string",
#     "color_preference": null | "string",
#     "budget": null | "number",
#     "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
#     "payment_method": null | "upi" | "card" | "pos",
#     "preferred_store": null | "string",
#     "use_loyalty": null | "boolean",
#     "confirm_payment": null | "boolean",
#     "city": null | "string"
#   },

#   "ready_to_buy": "boolean",

#   "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "checkout" | "loyalty" | "payment" | "confirm",

#   "plan_notes": "string",

#   "meta": {
#     "rec_query": null | "string",
#     "sku": null | "string",
#     "qty": null | "number",
#     "confirm_selection": null | "boolean",
#     "add": null | "string",
#     "product_id": null | "string",
#     "profile": null | "object",
#     "show_product_details": null | "boolean",
#     "check_availability": null | "boolean",
#     "upsell_trigger": null | "boolean"
#   }
# }

# ──────────────────────────────────────────────────────────────
# POST-PURCHASE INTENT RULES
# ──────────────────────────────────────────────────────────────
# If user asks about:
# - Tracking, "Where is my order?", "Status of delivery" -> Set intent = "postpurchase".
# - Returning, "I want to return", "Exchange this" -> Set intent = "postpurchase".
# - Feedback, "Leave a review", "Rate this" -> Set intent = "postpurchase".

# For these intents, plan must include: ["postpurchase_agent"].
# ──────────────────────────────────────────────────────────────
# OUTPUT RULES
# ──────────────────────────────────────────────────────────────
# - Message: Short, persuasive, consultative.
# - Ask: Max 1 question at a time.
# """


        self.system_prompt = system_prompt or """
You are "Aura," a Top-Tier Retail Sales Associate for a premium fashion brand. 
RESPOND IN JSON ONLY.

AVAILABLE_AGENTS: rec_agent, inventory_agent, cart_agent, payment_agent, order_agent, loyalty_agent, fulfillment_agent, postpurchase_agent

──────────────────────────────────────────────────────────────
🧠 SALES PSYCHOLOGY & BEHAVIOR (CRITICAL)
──────────────────────────────────────────────────────────────
1. NEVER be a "Vending Machine". Do not just dump product lists immediately unless the user is very specific.
2. THE CONSULTATIVE LOOP:
   - If user says "Show me shirts": 
     ❌ Bad: "Here are 5 shirts."
     ✅ Good: "I'd love to help! Are you looking for something formal for work, or a casual weekend vibe?"
   - Ask ONE clarifying question at a time (Occasion, Fit, Fabric, or Color).

3. THE UPSELL (Cross-Selling):
   - If the user selects a Product (e.g., a Suit), suggest a complement (e.g., a Tie or Pocket Square) before checkout.
   - Use phrases like: "That jacket is a great choice. It pairs perfectly with these chinos..."

4. CONTEXT AWARENESS:
   - Check UserProfile.city. If they are in "Guntur", prioritize mentions of the Guntur store.
   - If UserProfile.loyalty_points > 1000, mention they have points to redeem.

──────────────────────────────────────────────────────────────
MEMORY & TRUTH SOURCE
──────────────────────────────────────────────────────────────
Use SessionMemory.profile + ConversationHistory as the SINGLE source of truth.
If information is already present in memory (e.g., size, city), DO NOT ask for it again.

──────────────────────────────────────────────────────────────
PRODUCT SELECTION & IDENTIFICATION RULES
──────────────────────────────────────────────────────────────
User signals for selection: "this looks good", "give me details", "I want this", "add this".

When product intent is detected, you MUST output:
"meta": {
  "sku": "<product_id>",
  "confirm_selection": true
}

Set intent = "buy" but ready_to_buy = false initially.

──────────────────────────────────────────────────────────────
PRODUCT ATTRIBUTE RESOLUTION
──────────────────────────────────────────────────────────────
When a product is selected, check its `attributes` (size/color).
- Ask ONLY for missing REQUIRED attributes.
- Present options EXACTLY as provided in the product data.
- Once attributes are resolved, transition to Fulfillment.

──────────────────────────────────────────────────────────────
FULFILLMENT & INVENTORY
──────────────────────────────────────────────────────────────
After attributes are resolved, ask:
“Would you like to reserve it in store to try, or **add it to your cart**?”
(Do NOT ask to 'ship' directly. Shipping happens inside checkout).

──────────────────────────────────────────────────────────────
CART ACTION RULES
──────────────────────────────────────────────────────────────
Trigger cart actions ONLY on explicit phrases like "add to cart" or "buy now".
- Include "cart_agent" in plan.
- Set meta.add = "product_id".
- **IMPORTANT**: The Cart Agent will handle the response asking "Look for something else or Checkout?". You do not need to generate this message.

──────────────────────────────────────────────────────────────
CHECKOUT FLOW (STRICT SEQUENCE)
──────────────────────────────────────────────────────────────
Do NOT skip steps. Payment Agent handles the logic, you provide the inputs.

1. START CHECKOUT: 
   - User says: "Checkout", "Buy Now", "Ship".
   - Set intent = "buy", ready_to_buy = true.
   - Plan: ["payment_agent"].
   - Note: Agent will ask about Loyalty.

2. LOYALTY ANSWER: 
   - User says: "Yes use points", "No", "Skip".
   - Set slots.use_loyalty = true OR false.
   - Set ready_to_buy = true.
   - Plan: ["payment_agent"].
   - Note: Agent will show Summary & ask for Payment Method.

3. PAYMENT METHOD SELECTION:
   - User says: "UPI", "Card", "Credit Card".
   - Set slots.payment_method = "upi" OR "card".
   - Set ready_to_buy = true.
   - Plan: ["payment_agent"].
   - Note: Agent will generate QR or Card UI.

──────────────────────────────────────────────────────────────
PRODUCT DETAIL INTENT
──────────────────────────────────────────────────────────────
If user asks to see details/features of a selected product:
- Set meta.show_product_details = true.
- Do NOT initiate checkout yet.

──────────────────────────────────────────────────────────────
STRICT JSON OUTPUT SCHEMA
──────────────────────────────────────────────────────────────
{
  "intent": "recommend" | "buy" | "postpurchase" | "other" | "profile" | "qualify",
  "plan": ["string"],
  "message": "string",
  "ask": ["string"],

  "slots": {
    "occasion": null | "string",
    "size": null | "string",
    "fit": null | "string",
    "color_preference": null | "string",
    "budget": null | "number",
    "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
    "payment_method": null | "upi" | "card" | "pos",
    "preferred_store": null | "string",
    "use_loyalty": null | "boolean",
    "confirm_payment": null | "boolean",
    "city": null | "string"
  },

  "ready_to_buy": "boolean",

  "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "checkout" | "loyalty" | "payment" | "confirm",

  "plan_notes": "string",

  "meta": {
    "rec_query": null | "string",
    "sku": null | "string",
    "qty": null | "number",
    "confirm_selection": null | "boolean",
    "add": null | "string",
    "product_id": null | "string",
    "profile": null | "object",
    "show_product_details": null | "boolean",
    "check_availability": null | "boolean",
    "upsell_trigger": null | "boolean"
  }
}

──────────────────────────────────────────────────────────────
POST-PURCHASE INTENT RULES
──────────────────────────────────────────────────────────────
If user asks about:
- Tracking, "Where is my order?", "Status of delivery" -> Set intent = "postpurchase".
- Returning, "I want to return", "Exchange this" -> Set intent = "postpurchase".
- Feedback, "Leave a review", "Rate this" -> Set intent = "postpurchase".

For these intents, plan must include: ["postpurchase_agent"].
──────────────────────────────────────────────────────────────
OUTPUT RULES
──────────────────────────────────────────────────────────────
- Message: Short, persuasive, consultative.
- Ask: Max 1 question at a time.
"""
        self.timeout = timeout

    async def call_openai(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 500
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            body = r.json()
            return body["choices"][0]["message"]["content"]

    async def call_gemini(self, prompt: str) -> str:
            print("[DEBUG][LLM] Gemini called")
            

            
            # 1. Check if client exists
            if not gemini_client:
                print("[ERROR] Gemini Client is None. Check GEMINI_API_KEY.")
                return "{}"

            try:
                # 2. Use the stable alias 'gemini-1.5-flash'
                # The SDK handles the 'models/' prefix automatically, so we don't strictly need it.
                response = gemini_client.models.generate_content(
                    model="models/gemini-2.5-flash", 
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=800,
                        response_mime_type="application/json",
                        system_instruction=self.system_prompt
                    )
                )
                return response.text
            except Exception as e:
                # 3. Catch errors so the server doesn't crash (500 Error)
                print(f"[ERROR] Gemini API Failed: {e}")
                # Return a safe fallback JSON so the graph continues
                return json.dumps({
                    "intent": "other", 
                    "message": "I am currently experiencing high traffic. Please try again.",
                    "plan": []
                })



    async def call_groq(self, prompt: str) -> str:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set")

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        print("groq is called")
        payload = {
            "model": "llama-3.3-70b-versatile",          # or "llama-3.1-8b-instant"
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 500,
            # strongly recommended since you expect strict JSON:
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",  # <- correct base + path
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            body = r.json()
            return body["choices"][0]["message"]["content"]
        



    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        
        user_text = ctx.get("incoming_text", "")
        session_memory = ctx.get("memory", {})
        history = ctx.get("history", []) or []
        recent_history = history[-10:]
        retrieved = await rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
        fewshot = {
            "intent": "recommend",
            "plan": ["rec_agent"],
            "message": "Here are some products you might like.",
            "ask": ["Would you like to see details for any of these?"],
            "slots": {"occasion": None,"size": None,"fit": None,"color_preference": None,"budget": None,"fulfillment": None,"payment_method": None,"preferred_store": None,"phone_or_whatsapp_ok": None},
            "ready_to_buy": False,
            "next_stage": "qualify",
            "plan_notes": "collect slots before checkout",
            "meta": {"rec_query": "men shirt"}
        }
        prompt = (
            f"SessionMemory: {json.dumps(session_memory)}\n"
            f"ConversationHistory: {json.dumps(recent_history)}\n"
            f"RetrievedProducts: {json.dumps(retrieved)}\n\n"
            f"ExampleJSON:\n{json.dumps(fewshot)}\n\n"
            f"User: {user_text}\n\n"
            "Respond strictly in JSON as specified."
        )
        if USE_GEMINI and GEMINI_API_KEY:
            print("[DEBUG][LLM] Using Gemini provider")
            out = await self.call_gemini(prompt)
        elif USE_GROQ and GROQ_API_KEY:
            out = await self.call_groq(prompt)
        elif OPENAI_API_KEY:
            out = await self.call_openai(prompt)
        else:
            raise RuntimeError("No LLM provider configured")
        
        # --- ROBUST JSON PARSING START ---
        import re
        
        # 1. Strip Markdown Code Blocks (Common cause of errors)
        clean_out = out.strip()
        if "```" in clean_out:
            # Remove ```json ... ``` wrappers
            clean_out = re.sub(r"^```[a-zA-Z]*\n", "", clean_out)
            clean_out = re.sub(r"\n```$", "", clean_out)
            
        try:
            # 2. Attempt clean parse
            parsed = json.loads(clean_out)
            
        except json.JSONDecodeError:
            try:
                # 3. Aggressive Regex Extraction (Find the first { ... } block)
                # re.DOTALL (re.S) allows matching across newlines
                match = re.search(r"(\{.*\})", out, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    # Attempt to fix common trailing comma errors
                    json_str = re.sub(r",\s*\}", "}", json_str) 
                    parsed = json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in regex match")
            except Exception as e:
                # 4. Safe Fallback (Prevents 500 Server Error)
                print(f"[ERROR] JSON Parsing Failed completely. Raw Output: {out[:100]}... Error: {e}")
                parsed = {
                    "intent": "other",
                    "plan": [],
                    "message": "I'm having trouble processing that request. Could you try rephrasing?", 
                    "notes": "json_parse_error", 
                    "raw": out
                }
        # --- ROBUST JSON PARSING END ---
        # try:
        #     parsed = json.loads(out)
        # except Exception:
            

        #     import re
        #     m = re.search(r"(\{.*\})", out, re.S)
        #     parsed = json.loads(m.group(1)) if m else {"intent": "other", "plan": [], "message": None, "notes": "no_json", "raw": out}
            
        intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
        plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
        message = parsed.get("message")
        notes = parsed.get("notes")
        meta = parsed.get("meta")
        ask = parsed.get("ask") or []
        slots = parsed.get("slots") or {}
        ready_to_buy = bool(parsed.get("ready_to_buy"))
        next_stage = parsed.get("next_stage") or "qualify"
        normalized = {
            "intent": intent,
            "plan": plan,
            "message": message,
            "notes": notes,
            "meta": meta,
            "ask": ask,
            "slots": slots,
            "ready_to_buy": ready_to_buy,
            "next_stage": next_stage,
            "raw": out
        }
        return NodeResult(normalized)


class RecAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {}) or {}
        llm_intent = nodouts.get("llm_intent") or {}
        meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None

        profile = (ctx.get("memory", {}) or {}).get("profile", {}) or {}
        pref_filters = {}
        if profile.get("size"):
            pref_filters["size"] = profile["size"]
        if profile.get("fit"):
            pref_filters["fit"] = profile["fit"]
        if profile.get("color_preference"):
            pref_filters["color"] = profile["color_preference"]
        if profile.get("budget"):
            pref_filters["budget"] = profile["budget"]

        # 1) Get recommendations (from meta or from user text)
        if meta:
            recs = await rec_agent.recommend_from_meta(meta, top_k=3)
            if not recs:
                recs = await rec_agent.simple_keyword_recommend(
                    meta.get("rec_query") or "",
                    top_k=3,
                    filters=pref_filters or meta.get("filters"),
                )
        else:
            user_text = ctx.get("incoming_text", "")
            recs = await rec_agent.simple_keyword_recommend(
                user_text,
                top_k=3,
                filters=pref_filters,
            )

        recs = recs or []
        for r in recs:
            r["complements"] = rec_agent.complementary_for(r)

        # 2) Try to deduce which product user is referring to by name / "this"
        user_text_l = (ctx.get("incoming_text") or "").lower()
        deduced = None
        if user_text_l:
            for r in recs:
                name = (r.get("name") or "").lower()
                if not name:
                    continue
                # If name is directly mentioned or user uses "this/that" after seeing recs
                if name in user_text_l or "this" in user_text_l or "that" in user_text_l:
                    deduced = r
                    break

        return NodeResult({"recs": recs, "deduced": deduced})
    
class InventoryAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {}) or {}
        llm = nodouts.get("llm_intent") or {}
        meta = llm.get("meta") or {}
        
        # 1. Get User Location from Profile
        profile = ctx.get("memory", {}).get("profile", {})
        user_city = (profile.get("city") or "").lower()

        selection = ctx.get("memory", {}).get("selection_state", {})
        product_id = (
            meta.get("sku")
            or meta.get("product_id")
            or selection.get("product_id")
        )

        if not product_id:
            return NodeResult({"available_stores": [], "out_of_stock": False})

        # 2. Query Inventory DB
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                text("SELECT store_id, location, stock, reserved FROM inventory WHERE product_id = :pid"),
                {"pid": product_id}
            )
            rows = rows.fetchall()

        stores = []
        local_store_found = False
        total_available = 0

        for r in rows:
            available = max((r.stock or 0) - (r.reserved or 0), 0)
            if available > 0:
                total_available += available
                is_local = user_city in r.location.lower() if user_city else False
                if is_local: 
                    local_store_found = True
                
                stores.append({
                    "store_id": r.store_id,
                    "location": r.location,
                    "available_qty": available,
                    "is_local": is_local
                })

        stores.sort(key=lambda x: x['is_local'], reverse=True)

        # 3. HANDLE OUT OF STOCK
        oos_status = total_available <= 0
        alternatives = []
        
        if oos_status:
            # Fetch recommendations for similar products
            query = meta.get("rec_query") or product_id
            print(f"[INVENTORY] Out of stock. Fetching alternatives for query: {query}")
            alternatives = await rec_agent.simple_keyword_recommend(query, top_k=3)
            # Filter out the current product from alternatives
            alternatives = [p for p in alternatives if p.get("product_id") != product_id]

        return NodeResult({
            "product_id": product_id,
            "available_stores": stores,
            "out_of_stock": oos_status, # <--- Hard Gate Flag
            "user_city": user_city,
            "local_store_found": local_store_found,
            "alternatives": alternatives,
            "message": "I'm sorry, I checked everywhere but this item is currently out of stock." if oos_status else None
        })

        
        
class PostPurchaseAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {})
        llm_intent = nodouts.get("llm_intent") or {}
        # We look at the 'intent' string from the LLM (e.g., "track", "return", "feedback")
        # Or we can look at specific slots/meta
        
        intent_type = llm_intent.get("intent") # "postpurchase"
        user_text = ctx.get("incoming_text", "").lower()
        user_id = ctx.get("user_id")
        
        if not user_id:
            return NodeResult({"message": "Please log in to manage orders."})

        # 1. TRACKING
        if any(x in user_text for x in ["track", "where", "status"]):
            data = await postpurchase_agent.track_order(user_id)
            if data["found"]:
                msg = (
                    f"📦 **Order {data['order_id']}**\n"
                    f"Status: **{data['status']}**\n"
                    f"Items: {data['items_count']} | Total: ₹{int(data['total'])}\n"
                    f"[Track Shipment]({data['tracking_link']})"
                )
                return NodeResult({"message": msg, "type": "tracking"})
            else:
                return NodeResult({"message": data["message"]})

        # 2. RETURNS
        elif any(x in user_text for x in ["return", "exchange", "refund"]):
            # Extract reason simply
            reason = "changed mind"
            if "defective" in user_text or "broken" in user_text: reason = "defective"
            elif "size" in user_text or "fit" in user_text: reason = "size issue"
            
            data = await postpurchase_agent.process_return(user_id, reason)
            return NodeResult({"message": data["message"], "type": "return"})

        # 3. FEEDBACK
        elif any(x in user_text for x in ["review", "feedback", "rating", "stars"]):
            # Mock rating extraction
            rating = 5
            if "bad" in user_text: rating = 2
            if "good" in user_text: rating = 4
            if "love" in user_text: rating = 5
            
            data = await postpurchase_agent.submit_feedback(user_id, rating, user_text)
            return NodeResult({"message": data["message"], "type": "feedback"})

        # Default Fallback
        return NodeResult({
            "message": "I can help you Track orders, Return items, or leave Feedback. What would you like to do?",
            "actions": ["Track Order", "Return Item", "Leave Feedback"]
        })


class CartAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        print("[DEBUG][CART_NODE] Starting run...")
        
        user_id = ctx.get("user_id", "anonymous")
        sid = ctx.get("session_id", "user:anon:web")
        channel = (sid.split(":")[-1] if ":" in sid else "web") or "web"

        nodouts = ctx.get("node_outputs", {}) or {}
        llm = nodouts.get("llm_intent") or {}
        meta = (llm.get("meta") or {}) if isinstance(llm, dict) else {}

        rec_out = nodouts.get("rec_agent") or {}
        recs = rec_out.get("recs", []) or []
        deduced = rec_out.get("deduced")

        qty = int(meta.get("qty", 1) or 1)

        # ✅ HARD GATE
        add_mode = meta.get("add")
        print(f"[DEBUG][CART_NODE] Add Mode detected: {add_mode}")

        if add_mode not in ("product_id", "first_rec"):
            print("[DEBUG][CART_NODE] Skipping: No valid add_mode set.")
            return NodeResult({"success": False, "message": None})

        # Helper to resolve product_id
        def resolve_product_id() -> Optional[str]:
            if meta.get("product_id"): return meta["product_id"]
            if meta.get("sku"): return meta["sku"]
            if isinstance(deduced, dict) and deduced.get("product_id"): return deduced["product_id"]
            if recs: return recs[0].get("product_id")
            return None

        pid = resolve_product_id()
        if not pid:
            print("[DEBUG][CART_NODE] Failed: Could not resolve Product ID.")
            return NodeResult({"success": False, "message": "No item to add yet."})
        
        print(f"[DEBUG][CART_NODE] Resolving Add for PID: {pid}")

        # 🔒 REAL-TIME STOCK CHECK
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                text("SELECT SUM(stock - reserved) as avail FROM inventory WHERE product_id = :pid"),
                {"pid": pid}
            )
            row = res.fetchone()
            available = row.avail if row and row.avail is not None else 0

        if available < qty:
            print(f"[DEBUG][CART_NODE] Out of Stock! Avail: {available}, Req: {qty}")
            return NodeResult({
                "success": False,
                "out_of_stock": True, 
                "message": f"I'm so sorry, SKU {pid} is out of stock."
            })

        # IF IN STOCK: Proceed with mutations
        if add_mode == "product_id":
            summary = await cart_agent.add_specific_to_cart(user_id, channel, pid, qty=qty)
        else: # first_rec
            summary = await cart_agent.add_first_rec_to_cart(user_id, channel, recs[0], qty=qty)
            
        print(f"[DEBUG][CART_NODE] Success. New Count: {summary['count']}")
        msg = (
            f"✅ Added to your cart. You have {summary['count']} item(s) for ₹{summary['subtotal']}.\n"
            "Would you like to look for something else, or check out now?"
        )
        return NodeResult({"success": True, "cart": summary, "message": msg})



class PaymentAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        from backend.db import AsyncSessionLocal
        from backend import crud as db_crud
        import uuid
        import time
        import json
        
        # Ensure we access the global redis client defined in this file
        # (Assuming 'redis' is defined at the top of master_graph.py)
        global redis 

        print(f"[DEBUG][PAYMENT_NODE] Starting run...") 
        
        nodouts = ctx.get("node_outputs", {})
        llm_intent = nodouts.get("llm_intent") or {}
        slots = llm_intent.get("slots") or {}
        
        user_id = ctx.get("user_id", "anonymous")
        sid = ctx.get("session_id", "user:anon:web")
        channel = (sid.split(":")[-1] if ":" in sid else "web") or "web"
        user_text = ctx.get("incoming_text", "").lower()

        # 1. Fetch Data
        async with AsyncSessionLocal() as session:
            cart = await db_crud.get_or_create_cart(session, user_id, channel)
            items = await db_crud.get_cart_items(session, cart.cart_id)
            loyalty_info = await db_crud.get_user_loyalty(session, user_id)

        if not items:
            return NodeResult({
                "success": False,
                "status": "empty_cart",
                "message": "Your cart is empty. Please add items first."
            })
            
        # Calculate Base Totals
        subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
        current_points = loyalty_info.get("points", 0)
        loyalty_value = current_points * 0.5 

        # --- LOGIC STEP 1: DETECT LOYALTY INTENT ---
        use_loyalty = slots.get("use_loyalty")
        
        if use_loyalty is None:
            if any(x in user_text for x in ["no", "nope", "cancel", "skip", "don't"]):
                use_loyalty = False
            elif any(x in user_text for x in ["yes", "sure", "ok", "use points", "redeem"]):
                use_loyalty = True

        if current_points > 0 and use_loyalty is None:
            max_discount = min(subtotal, loyalty_value)
            return NodeResult({
                "success": False,
                "status": "needs_loyalty_decision",
                "message": (
                    f"You have **{current_points} Loyalty Points** (Value: ₹{int(loyalty_value)}).\n"
                    f"Would you like to redeem them to save ₹{int(max_discount)}?"
                )
            })

        # --- LOGIC STEP 2: CALCULATE FINAL TOTALS ---
        loyalty_discount = 0.0
        points_used = 0
        if use_loyalty is True and current_points > 0:
            loyalty_discount = min(subtotal, loyalty_value)
            points_used = int(loyalty_discount / 0.5)
            
        final_amount = subtotal - loyalty_discount

        item_details_text = ""
        for i in items:
            p_name = i.product_id 
            item_details_text += f"- {p_name} (x{i.qty}): ₹{int(i.price_at_add) * i.qty}\n"

        # --- LOGIC STEP 3: CHECK PAYMENT METHOD ---
        payment_method = slots.get("payment_method")
        
        if not payment_method:
            if "upi" in user_text: payment_method = "upi"
            elif "card" in user_text or "debit" in user_text or "credit" in user_text: payment_method = "card"

        if not payment_method:
            msg = (
                f"🧾 **Order Summary**\n"
                f"{item_details_text}"
                f"----------------\n"
                f"Subtotal: ₹{int(subtotal)}\n"
            )
            if loyalty_discount > 0:
                msg += f"Loyalty Discount: -₹{int(loyalty_discount)} ({points_used} pts used)\n"
            
            msg += f"**Final Total: ₹{int(final_amount)}**\n\n"
            msg += "How would you like to pay? (UPI or Card)"
            
            return NodeResult({
                "success": True, 
                "status": "awaiting_payment_method",
                "message": msg,
                "final_amount": final_amount
            })

        # --- LOGIC STEP 4: EXECUTE PAYMENT ---
        intent_id = "ORD-" + uuid.uuid4().hex[:8]
        
        # Save intent to Redis so it can be verified/regenerated later
        intent_data = {
            "payment_intent_id": intent_id,
            "amount": final_amount,
            "status": "pending",
            "product_id": items[0].product_id if items else "unknown",
            "qty": sum(i.qty for i in items),
            "created_at": time.time(),
            "expires_at": time.time() + 300
        }
        
        # 🔥 CRITICAL: Write to Redis and Log it
        redis_key = f"payment_intent:{intent_id}"
        await redis.set(redis_key, json.dumps(intent_data), ex=300)
        print(f"[DEBUG][PAYMENT_NODE] Saved Intent to Redis: {redis_key}")

        if payment_method == "upi":
            qr_data = f"upi://pay?pa=retailco@upi&am={final_amount:.2f}&tn={intent_id}"
            return NodeResult({
                "success": True,
                "status": "pending_payment",
                "payment_intent_id": intent_id,
                "payment_type": "upi",
                "qr_data": qr_data, 
                "amount": final_amount,
                "message": f"Generated UPI QR for ₹{int(final_amount)}. Please scan to pay.\n(Click 'I have paid' when done)."
            })
            
        elif payment_method == "card":
            return NodeResult({
                "success": True,
                "status": "pending_payment",
                "payment_intent_id": intent_id,
                "payment_type": "card",
                "show_card_ui": True, 
                "amount": final_amount,
                "message": f"Please enter your card details for ₹{int(final_amount)} secure payment."
            })
        
        else:
             return NodeResult({"success": False, "message": "Invalid payment method. Please choose UPI or Card."})
# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         from backend.db import AsyncSessionLocal
#         from backend import crud as db_crud

#         print(f"[DEBUG][PAYMENT_NODE] Starting run...") 
        
#         nodouts = ctx.get("node_outputs", {})
#         llm_intent = nodouts.get("llm_intent") or {}
#         slots = llm_intent.get("slots") or {}
        
#         user_id = ctx.get("user_id", "anonymous")
#         sid = ctx.get("session_id", "user:anon:web")
#         channel = (sid.split(":")[-1] if ":" in sid else "web") or "web"
#         user_text = ctx.get("incoming_text", "").lower()

#         # 1. Fetch Data
#         async with AsyncSessionLocal() as session:
#             cart = await db_crud.get_or_create_cart(session, user_id, channel)
#             items = await db_crud.get_cart_items(session, cart.cart_id)
#             loyalty_info = await db_crud.get_user_loyalty(session, user_id)

#         if not items:
#             return NodeResult({
#                 "success": False,
#                 "status": "empty_cart",
#                 "message": "Your cart is empty. Please add items first."
#             })
            
#         # Calculate Base Totals
#         subtotal = sum([float(i.price_at_add or 0) * int(i.qty or 1) for i in items])
#         current_points = loyalty_info.get("points", 0)
#         loyalty_value = current_points * 0.5  # 1 Point = ₹0.50

#         # --- LOGIC STEP 1: DETECT LOYALTY INTENT ---
#         use_loyalty = slots.get("use_loyalty")
        
#         # Fallback keyword detection for boolean slots
#         if use_loyalty is None:
#             if any(x in user_text for x in ["no", "nope", "cancel", "skip", "don't"]):
#                 use_loyalty = False
#             elif any(x in user_text for x in ["yes", "sure", "ok", "use points", "redeem"]):
#                 use_loyalty = True

#         # IF points exist AND user hasn't decided yet -> ASK
#         if current_points > 0 and use_loyalty is None:
#             max_discount = min(subtotal, loyalty_value)
#             return NodeResult({
#                 "success": False,
#                 "status": "needs_loyalty_decision",
#                 "message": (
#                     f"You have **{current_points} Loyalty Points** (Value: ₹{int(loyalty_value)}).\n"
#                     f"Would you like to redeem them to save ₹{int(max_discount)}?"
#                 )
#             })

#         # --- LOGIC STEP 2: CALCULATE FINAL TOTALS ---
#         loyalty_discount = 0.0
#         points_used = 0
#         if use_loyalty is True and current_points > 0:
#             loyalty_discount = min(subtotal, loyalty_value)
#             points_used = int(loyalty_discount / 0.5)
            
#         final_amount = subtotal - loyalty_discount

#         # Detailed Item List for Summary
#         item_details_text = ""
#         for i in items:
#             p_name = i.product_id # Ideally fetch name, using ID for now
#             item_details_text += f"- {p_name} (x{i.qty}): ₹{int(i.price_at_add) * i.qty}\n"

#         # --- LOGIC STEP 3: CHECK PAYMENT METHOD ---
#         payment_method = slots.get("payment_method")
        
#         # Fallback keyword detection for payment method
#         if not payment_method:
#             if "upi" in user_text: payment_method = "upi"
#             elif "card" in user_text or "debit" in user_text or "credit" in user_text: payment_method = "card"

#         # If NO payment method selected yet -> SHOW SUMMARY & ASK
#         if not payment_method:
#             msg = (
#                 f"🧾 **Order Summary**\n"
#                 f"{item_details_text}"
#                 f"----------------\n"
#                 f"Subtotal: ₹{int(subtotal)}\n"
#             )
#             if loyalty_discount > 0:
#                 msg += f"Loyalty Discount: -₹{int(loyalty_discount)} ({points_used} pts used)\n"
            
#             msg += f"**Final Total: ₹{int(final_amount)}**\n\n"
#             msg += "How would you like to pay? (UPI or Card)"
            
#             return NodeResult({
#                 "success": True, 
#                 "status": "awaiting_payment_method",
#                 "message": msg,
#                 "final_amount": final_amount
#             })

#         # --- LOGIC STEP 4: EXECUTE PAYMENT ---
#         intent_id = "ORD-" + uuid.uuid4().hex[:8]
        
#         if payment_method == "upi":
#             qr_data = f"upi://pay?pa=retailco@upi&am={final_amount:.2f}&tn={intent_id}"
#             return NodeResult({
#                 "success": True,
#                 "status": "payment_pending",
#                 "payment_intent_id": intent_id,
#                 "payment_type": "upi",
#                 "qr_data": qr_data, # Frontend should render this as QR
#                 "amount": final_amount,
#                 "message": f"Generated UPI QR for ₹{int(final_amount)}. Please scan to pay.\n(Click 'I have paid' when done)."
#             })
            
#         elif payment_method == "card":
#             return NodeResult({
#                 "success": True,
#                 "status": "payment_pending",
#                 "payment_intent_id": intent_id,
#                 "payment_type": "card",
#                 "show_card_ui": True, # Frontend triggers fake card modal
#                 "amount": final_amount,
#                 "message": f"Please enter your card details for ₹{int(final_amount)} secure payment."
#             })
        
#         else:
#              return NodeResult({"success": False, "message": "Invalid payment method. Please choose UPI or Card."})

class OrderAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        user_id = ctx.get("user_id")
        if not user_id:
            return NodeResult({"orders": [], "error": "no_user"})
        async with AsyncSessionLocal() as session:
            try:
                rows = await db_crud.get_orders_for_user(session, user_id)
                orders = [{"order_id": r.order_id, "status": r.status, "items": r.items, "created_at": str(r.created_at)} for r in rows]
                return NodeResult({"orders": orders})
            except Exception as e:
                return NodeResult({"orders": [], "error": str(e)})
            

        
# class FulfillmentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         from backend.db import AsyncSessionLocal
#         from backend import crud

#         nodouts = ctx.get("node_outputs", {})
#         llm = nodouts.get("llm_intent") or {}
#         slots = llm.get("slots") or {}

#         fulfillment = slots.get("fulfillment")
#         if fulfillment != "reserve_in_store":
#             return NodeResult({"mode": fulfillment})

#         user_id = ctx.get("user_id")
#         selection = ctx.get("memory", {}).get("selection_state", {})
#         product_id = selection.get("product_id")

#         inv = nodouts.get("inventory_agent") or {}
#         stores = inv.get("available_stores", [])

#         if not stores or not product_id:
#             return NodeResult({
#                 "success": False,
#                 "message": "Unable to reserve — product or store not available."
#             })

#         store_id = stores[0]["store_id"]

#         async with AsyncSessionLocal() as db:
#             reservation = await crud.create_reservation(
#                 db=db,
#                 user_id=user_id,
#                 product_id=product_id,
#                 store_id=store_id,
#                 qty=1,
#                 hold_minutes=45,
#             )

#         if not reservation:
#             return NodeResult({
#                 "success": False,
#                 "message": "Sorry — someone just reserved the last piece."
#             })

#         # 🔒 HARD STATE UPDATE (BACKEND OWNS THIS)
#         ctx["memory"]["stage"] = STAGES["CART"]
#         ctx["memory"]["reservation"] = reservation

#         return NodeResult({
#             "success": True,
#             "mode": "reserve_in_store",
#             "reservation": reservation,
#             "message": (
#                 f"✅ Reserved successfully at store {store_id}. "
#                 f"Please visit within 45 minutes and mention code {reservation['reservation_id']}."
#             )
#         })

# backend/agents/master_graph.py

# backend/agents/master_graph.py

# backend/agents/master_graph.py

# backend/agents/master_graph.py

class FulfillmentAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        from backend.db import AsyncSessionLocal
        from backend import crud

        user_id = ctx.get("user_id")
        
        # 1. Access Session Memory
        memory = ctx.get("memory", {})
        selection = memory.get("selection_state", {})
        reservation_mem = memory.get("reservation", {}) 

        product_id = selection.get("product_id")
        store_id = reservation_mem.get("store_id")

        # 2. Fallback logic for Store ID
        if not store_id:
            nodouts = ctx.get("node_outputs", {})
            inv = nodouts.get("inventory_agent") or {}
            stores = inv.get("available_stores", [])
            if stores:
                store_id = stores[0]["store_id"]

        # --- 🛑 STOPGAP: ASK FOR MISSING INFO ---
        
        # A. Missing Store?
        if not store_id:
            return NodeResult({
                "success": False,
                "message": "Sure! Which store would you like to reserve this at?",
                "next_stage": "reserve_in_store" # Keep user in this stage
            })

        # B. Missing Date?
        if not reservation_mem.get("date"):
            return NodeResult({
                "success": False,
                "message": f"You've selected store {store_id}. What date would you like to come in?",
                "next_stage": "reserve_in_store" # Keep user in this stage
            })

        # C. Missing Time?
        if not reservation_mem.get("time"):
             return NodeResult({
                "success": False,
                "message": f"Got it, {reservation_mem['date']}. What time works best for you?",
                "next_stage": "reserve_in_store" # Keep user in this stage
            })

        # --- ✅ ALL DATA PRESENT: SAVE TO DB ---

        r_date = reservation_mem.get("date")
        r_time = reservation_mem.get("time")

        async with AsyncSessionLocal() as db:
            res_id = await crud.create_reservation(
                db=db,
                user_id=user_id,
                product_id=product_id,
                store_id=store_id,
                date=r_date,
                time=r_time
            )

        if not res_id:
             return NodeResult({"success": False, "message": "Database error."})

        reservation_obj = {
            "reservation_id": res_id,
            "store_id": store_id,
            "product_id": product_id,
            "date": r_date,
            "time": r_time,
            "status": "active"
        }

        # 4. Update State to CART (Finished)
        ctx["memory"]["stage"] = STAGES["CART"]
        ctx["memory"]["reservation"] = reservation_obj

        return NodeResult({
            "success": True,
            "mode": "reserve_in_store",
            "reservation": reservation_obj,
            "message": (
                f"✅ Reserved successfully at store {store_id}. "
                f"Please visit on {r_date} at {r_time}. Your code is {res_id}."
            )
        })

            
class PostPurchaseAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        # Very simple stub: just describes what we *could* do.
        nodouts = ctx.get("node_outputs", {})
        orders = (nodouts.get("order_agent") or {}).get("orders", [])
        if not orders:
            return NodeResult({
                "message": "I don't see any recent orders linked to your profile yet. Once you place an order, I can help you track it or start a return.",
                "actions": []
            })
        latest = orders[0]
        return NodeResult({
            "message": f"Your latest order {latest['order_id']} is currently {latest['status']}. I can help you with tracking, returns or exchanges.",
            "actions": ["track", "return", "exchange"]
        })
        






def _canonicalize_session_id(raw_sid: str, user_id: Optional[str], default_channel: str = "web") -> str:
    channel = default_channel
    if ":" in (raw_sid or ""):
        channel = (raw_sid.split(":")[0] or default_channel).lower()
    if user_id:
        return f"user:{user_id}:{channel}"
    return raw_sid
def get_missing_attributes(product: Dict[str, Any], selected_attrs: Dict[str, Any]):
    missing = []
    attributes = product.get("attributes", {}) or {}

    for attr_name, attr_def in attributes.items():
        if not isinstance(attr_def, dict):
            continue

        required = attr_def.get("required", False)
        options = attr_def.get("options", [])

        if required and not selected_attrs.get(attr_name):
            missing.append({
                "name": attr_name,
                "options": options
            })

    return missing


def render_product_details(product: dict) -> dict:
    return {
        "product_id": product.get("product_id"),
        "name": product.get("name"),
        "price": product.get("price"),
        "category": product.get("category"),
        "description": product.get("description"),
        "attributes": product.get("attributes", {}),
        "images": product.get("images", []),
        "complements": product.get("complements", [])
    }
    
    
    
async def run_master(session_id: str, incoming_text: str, user_meta: Optional[Dict[str, Any]] = None):
    # RENAME ARGUMENT 'text' -> 'incoming_text'
    print(f"\n[DEBUG][MASTER] Incoming: '{incoming_text}' Session: {session_id}")
    
    user_id = (user_meta or {}).get("user_id")
    canonical_sid = _canonicalize_session_id(session_id, user_id=user_id, default_channel="web")
    if canonical_sid != session_id:
        try:
            await merge_sessions(session_id, canonical_sid, keep_last=10)
        except Exception:
            pass
        session_id = canonical_sid
    try:
        active_sid = await get_active_session_for_user(user_id) if user_id else None
        if active_sid and active_sid != session_id:
            await merge_sessions(active_sid, session_id, keep_last=10)
    except Exception:
        pass
    session = await load_session(session_id)
    profile = await load_user_profile(user_id) 
    
    # ================================
    # 🔒 SESSION MEMORY INITIALIZATION
    # ================================
    session.setdefault("memory", {})
    session["memory"].setdefault("stage", STAGES["RECOMMEND"])
    session["memory"].setdefault("selection_state", {
        "product_id": None,
        "selected_attributes": {},
    })
    session["memory"].setdefault("reservation", {
        "store_id": None,
        "date": None,
        "time": None,
    })

    # ================================
    # BACKEND RESERVE INPUT PARSER
    # ================================
    if session["memory"]["stage"] == STAGES["RESERVE"]:
        reservation = session["memory"]["reservation"]
        user_text = (incoming_text or "").lower()
        import re
        if not reservation.get("store_id"):
            m = re.search(r"\b(s\d+)\b", user_text)
            if m: reservation["store_id"] = m.group(1).upper()
        if not reservation.get("date"):
            if "today" in user_text: reservation["date"] = "today"
            elif "tomorrow" in user_text: reservation["date"] = "tomorrow"
            else:
                m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", user_text)
                if m: reservation["date"] = m.group(1)
        if not reservation.get("time"):
            m = re.search(r"\b(\d{1,2})(?:\s*:\s*(\d{2}))?\s*(am|pm)?\b", user_text)
            if m:
                hour = m.group(1)
                minute = m.group(2) or "00"
                meridian = m.group(3) or ""
                reservation["time"] = f"{hour}:{minute} {meridian}".strip()
        session["memory"]["reservation"] = reservation

    ctx = {
        "session_id": session_id,
        "user_id": user_id,
        "incoming_text": incoming_text,
        "memory": session.get("memory", {}),
        "history": session.get("history", []),
        "node_outputs": {}
    }

    g = AgentGraph(graph_id=f"master-{session_id[:8]}")
    llm_node = LLMAgentNode()
    rec_node = RecAgentNode("rec_agent")
    cart_node = CartAgentNode("cart_agent")
    inventory_node = InventoryAgentNode("inventory_agent")
    pay_node = PaymentAgentNode("payment_agent")
    order_node = OrderAgentNode("order_agent")
    loyalty_node = LoyaltyAgentNode("loyalty_agent")
    fulfill_node = FulfillmentAgentNode("fulfillment_agent")
    postpurchase_node = PostPurchaseAgentNode("postpurchase_agent")

    for n in [llm_node, rec_node,  inventory_node, cart_node, pay_node, order_node, loyalty_node, fulfill_node, postpurchase_node]:
        g.add_node(n)

    # 1. RUN LLM INTENT
    intent_res = await llm_node.run(ctx)
    ctx["node_outputs"]["llm_intent"] = intent_res.output
    intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
    intent = intent_out.get("intent", "other")
    plan = intent_out.get("plan", []) or []
    slots = (intent_out.get("slots") or {}) if isinstance(intent_out, dict) else {}
    ready_to_buy = bool(intent_out.get("ready_to_buy"))
    next_stage = intent_out.get("next_stage") or "qualify"
    meta = intent_out.get("meta") or {}
    
    user_text_lower = (incoming_text or "").lower()

    # ======================================================
    # 🔥 FIXED: GLOBAL INTENT & STATE TRIGGERS
    # ======================================================
    
    # A) Global "Add to Cart" Trigger (Bypasses LLM hallucinations)
    if any(x in user_text_lower for x in ["add to cart", "buy this", "add this", "add it"]):
        print("[DEBUG][MASTER] Global 'Add to Cart' Triggered")
        plan = ["cart_agent"]
        meta["add"] = "product_id" # Force the flag
        # If we have a selected product, ensure SKU is passed
        if session["memory"]["selection_state"].get("product_id"):
            meta["sku"] = session["memory"]["selection_state"]["product_id"]

    # B) Global "Checkout" Trigger
    is_checkout_intent = any(x in user_text_lower for x in ["checkout", "ship", "ship to address", "buy now"])
    if is_checkout_intent:
        print("[DEBUG][MASTER] Global 'Checkout' Triggered")
        session["memory"]["stage"] = STAGES["CHECKOUT"]
        ready_to_buy = True
        plan = ["payment_agent"] 

    # C) Global "Reserve" Trigger
    if "reserve" in user_text_lower and session["memory"]["stage"] != STAGES["RESERVE"]:
        if session["memory"]["selection_state"].get("product_id") or meta.get("sku"):
             print("[DEBUG][MASTER] Global 'Reserve' Triggered")
             session["memory"]["stage"] = STAGES["RESERVE"]
             if meta.get("sku"):
                 session["memory"]["selection_state"]["product_id"] = meta["sku"]
             await save_session(session_id, session)
             return {
                "session_id": session_id,
                "results": {"message": "Sure! Which store would you like to reserve this at?"},
                "next_stage": STAGES["RESERVE"],
            }

    # ======================================================
    # 🔥 FIXED: HARD PLAN OVERRIDE
    # ======================================================
    stage = session["memory"].get("stage", STAGES["RECOMMEND"])
    print(f"[DEBUG][MASTER] Current Stage: {stage}")

    # Logic to ensure plans match stage logic
    if stage == STAGES["RECOMMEND"]:
        if "cart_agent" not in plan: plan = ["rec_agent"]
    elif stage == STAGES["PRODUCT_DETAILS"]:
        # Allow inventory or cart if specifically asked, else just show details
        if "cart_agent" in plan: pass # Allow add
        elif "inventory_agent" in plan or meta.get("check_availability"): plan = ["inventory_agent"]
        else: plan = [] 
    elif stage == STAGES["AVAILABILITY"]:
         if "cart_agent" not in plan: plan = ["inventory_agent"]
    elif stage == STAGES["RESERVE"]:
        plan = ["fulfillment_agent"]
    elif stage == STAGES["CART"]:
        plan = ["cart_agent"]
    elif stage == STAGES["CHECKOUT"]:
        plan = ["payment_agent"]
    elif stage == STAGES["PAYMENT"]:
        plan = ["payment_agent"] # Keep ensuring payment agent runs in payment loop

    # 🚫 Remove inventory if already reserved
    if session["memory"]["selection_state"].get("reserved") is True:
        plan = [p for p in plan if p != "inventory_agent"]

    # 🔒 Block payment unless checkout/payment
    if session["memory"]["stage"] not in (STAGES["CHECKOUT"], STAGES["PAYMENT"]):
        plan = [p for p in plan if p not in ("payment_agent", "loyalty_agent", "order_agent")]

    print(f"[DEBUG][MASTER] Final Execution Plan: {plan}")

    # ================================
    # EXECUTE GRAPH
    # ================================
    from difflib import get_close_matches
    validated_plan = []
    
    # Normalize plan node names
    for nid in plan:
        if nid in g.nodes:
            validated_plan.append(nid)
        else:
            matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
            if matches: validated_plan.append(matches[0])

    final = {"session_id": session_id, "intent": intent, "results": {}}
    
    # Run Agents
    for node_id in validated_plan:
        print(f"[DEBUG][MASTER] Running Node: {node_id}")
        res = await g.nodes[node_id].run(ctx)
        ctx["node_outputs"][node_id] = res.output

        # 🛑 STOCK CHECK GATEKEEPER
        if isinstance(res.output, dict) and res.output.get("out_of_stock"):
            print("[DEBUG][MASTER] Caught Out of Stock. Stopping Chain.")
            session["memory"]["stage"] = STAGES["AVAILABILITY"]
            session["memory"]["selection_state"]["out_of_stock"] = True
            final["results"]["message"] = res.output.get("message")
            final["results"]["out_of_stock"] = True
            if res.output.get("alternatives"):
                final["results"]["items"] = res.output.get("alternatives")
            await save_session(session_id, session)
            return final

    # ================================
    # POST-EXECUTION STATE UPDATES
    # ================================
    outs = ctx["node_outputs"]
    
    # Pass Loyalty Data to Frontend if available
    if "loyalty_agent" in outs:
        final["results"]["loyalty"] = outs["loyalty_agent"]
        print(f"[DEBUG][MASTER] Loyalty info attached: {outs['loyalty_agent'].get('points')} points")
    
    # Update Profile
    if isinstance(meta, dict):
        profile_patch = meta.get("profile") or {}
        if profile_patch and user_id:
            await save_user_profile(user_id, profile_patch)
            session["memory"].setdefault("profile", {}).update(profile_patch)

    # Capture Product Selection
    selection_state = session["memory"].get("selection_state", {})
    if meta.get("sku") and meta.get("sku") != selection_state.get("product_id"):
        selection_state.pop("out_of_stock", None)
        selection_state["product_id"] = meta.get("sku")
        session["memory"]["selection_state"] = selection_state

    # ================================
    # 🔥 FIXED: RENDER RESULTS (Products & Details)
    # ================================
    
    # Get active product object
    active_pid = selection_state.get("product_id")
    recs = []
    if "rec_agent" in outs: recs = outs["rec_agent"].get("recs", [])
    
    active_product = None
    for p in recs:
        if p.get("product_id") == active_pid: 
            active_product = p
            break
    if not active_product and active_pid:
        active_product = await rec_agent.get_product_by_sku(active_pid)

    # STEP B: SHOW PRODUCT DETAILS
    if active_product and meta.get("show_product_details") is True:
        session["memory"]["stage"] = STAGES["PRODUCT_DETAILS"]
        
        # Populate details for UI
        final["results"]["product_details"] = {
            "product_id": active_product.get("product_id"),
            "name": active_product.get("name"),
            "price": float(active_product.get("price", 0)),
            "description": active_product.get("description"),
            "attributes": active_product.get("attributes", {}),
            "images": active_product.get("images", []),
        }
        
        # 🔥 FIX: Populate 'items' array so Card shows up
        final["results"]["items"] = [{
            "product_id": active_product.get("product_id"),
            "name": active_product.get("name"),
            "price": float(active_product.get("price", 0)),
            "image": (active_product.get("images") or [None])[0],
            "attributes": active_product.get("attributes", {})
        }]

        final["results"]["message"] = f"{active_product.get('name')} is ₹{int(active_product.get('price', 0))}."
        final["results"]["ask"] = ["Add to cart?", "Check availability?"]
        await save_session(session_id, session)
        return final

    # ================================
    # FINAL MESSAGE CONSTRUCTION
    # ================================
    
    # 🔥 FIX: Priority Override - TRUST AGENTS OVER LLM
    llm_msg = intent_out.get("message")
    final["results"]["message"] = llm_msg # Default

    if "cart_agent" in outs and outs["cart_agent"].get("message"):
        print("[DEBUG][MASTER] Overriding message with Cart Agent output")
        final["results"]["message"] = outs["cart_agent"]["message"]
        
    elif "inventory_agent" in outs and outs["inventory_agent"].get("message"):
        print("[DEBUG][MASTER] Overriding message with Inventory Agent output")
        final["results"]["message"] = outs["inventory_agent"]["message"]

    elif "payment_agent" in outs:
        # Pass through payment agent messages (QR codes, loyalty questions)
        pay_res = outs["payment_agent"]
        final["results"]["order"] = pay_res
        if pay_res.get("message"):
            final["results"]["message"] = pay_res["message"]
    
    # Populate generic items list if available
    items = []
    if recs and not final["results"].get("items"):
         for p in recs:
            items.append({
                "product_id": p.get("product_id"),
                "name": p.get("name"),
                "price": float(p.get("price", 0)),
                "image": (p.get("images") or [None])[0],
                "category": p.get("category"),
            })
         final["results"]["items"] = items

    # Save Session
    session.setdefault("history", []).append({
        "incoming": incoming_text,
        "intent": intent,
        "results": final["results"],
        "next_stage": session["memory"]["stage"]
    })
    session["last_updated"] = __import__("time").time()
    await save_session(session_id, session)
    
    return final


# async def run_master(session_id: str, incoming_text: str, user_meta: Optional[Dict[str, Any]] = None):
#     # RENAME ARGUMENT 'text' -> 'incoming_text'
    
#     user_id = (user_meta or {}).get("user_id")
#     canonical_sid = _canonicalize_session_id(session_id, user_id=user_id, default_channel="web")
#     if canonical_sid != session_id:
#         try:
#             await merge_sessions(session_id, canonical_sid, keep_last=10)
#         except Exception:
#             pass
#         session_id = canonical_sid
#     try:
#         active_sid = await get_active_session_for_user(user_id) if user_id else None
#         if active_sid and active_sid != session_id:
#             await merge_sessions(active_sid, session_id, keep_last=10)
#     except Exception:
#         pass
#     session = await load_session(session_id)
#     profile = await load_user_profile(user_id) 
    
    
#     # ================================
#     # 🔒 SESSION MEMORY INITIALIZATION (MUST BE FIRST)
#     # ================================
#     session.setdefault("memory", {})
#     session["memory"].setdefault("stage", STAGES["RECOMMEND"])
#     session["memory"].setdefault("selection_state", {
#         "product_id": None,
#         "selected_attributes": {},
#     })
#     session["memory"].setdefault("reservation", {
#         "store_id": None,
#         "date": None,
#         "time": None,
#     })

    
    
    
    
    
#     # ================================
#     # BACKEND RESERVE INPUT PARSER
#     # ================================
#     if session["memory"]["stage"] == STAGES["RESERVE"]:
#         reservation = session["memory"]["reservation"]
#         user_text = (incoming_text or "").lower()

#         # ---- Store ID (S1, s1, store s1) ----
#         import re

#         if not reservation.get("store_id"):
#             m = re.search(r"\b(s\d+)\b", user_text)
#             if m:
#                 reservation["store_id"] = m.group(1).upper()

#         # ---- Date parsing (simple) ----
#         if not reservation.get("date"):
#             if "today" in user_text:
#                 reservation["date"] = "today"
#             elif "tomorrow" in user_text:
#                 reservation["date"] = "tomorrow"
#             else:
#                 m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", user_text)
#                 if m:
#                     reservation["date"] = m.group(1)

#         # ---- Time parsing ----
#         if not reservation.get("time"):
#             m = re.search(r"\b(\d{1,2})(?:\s*:\s*(\d{2}))?\s*(am|pm)?\b", user_text)
#             if m:
#                 hour = m.group(1)
#                 minute = m.group(2) or "00"
#                 meridian = m.group(3) or ""
#                 reservation["time"] = f"{hour}:{minute} {meridian}".strip()

#         session["memory"]["reservation"] = reservation

#         print("[DEBUG][PARSE] reservation now =", reservation)

    



#     ctx = {
#         "session_id": session_id,
#         "user_id": user_id,
#         "incoming_text": incoming_text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     cart_node = CartAgentNode("cart_agent")
#     inventory_node = InventoryAgentNode("inventory_agent")
#     pay_node = PaymentAgentNode("payment_agent")
#     order_node = OrderAgentNode("order_agent")
#     loyalty_node = LoyaltyAgentNode("loyalty_agent")
#     fulfill_node = FulfillmentAgentNode("fulfillment_agent")
#     postpurchase_node = PostPurchaseAgentNode("postpurchase_agent")

#     for n in [llm_node, rec_node,  inventory_node, cart_node, pay_node, order_node, loyalty_node, fulfill_node, postpurchase_node]:
#         g.add_node(n)


#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []
#     slots = (intent_out.get("slots") or {}) if isinstance(intent_out, dict) else {}
#     ready_to_buy = bool(intent_out.get("ready_to_buy"))
#     next_stage = intent_out.get("next_stage") or "qualify"
#     meta = intent_out.get("meta") or {}
    
#     user_text_lower = (incoming_text or "").lower()

#     # ================================
#     # 🩹 FIX: INTERPRET "SHIP TO ADDRESS" OR "CHECKOUT"
#     # ================================
#     is_checkout_intent = any(x in user_text_lower for x in ["checkout", "ship", "ship to address", "buy now"])
    
#     # If user says "Ship/Checkout", force Payment Stage
#     if is_checkout_intent:
#         session["memory"]["stage"] = STAGES["CHECKOUT"]
#         ready_to_buy = True
#         plan = ["payment_agent"] # Ensure payment agent runs
    
    
#     # ================================
#     # 🩹 FIX 2: GLOBAL RESERVE TRANSITION (Pre-Execution)
#     # Allows "reserve" command to work from ANY stage
#     # ================================
#     if "reserve" in user_text_lower and session["memory"]["stage"] != STAGES["RESERVE"]:
#         # Only if product is selected
#         if session["memory"]["selection_state"].get("product_id") or meta.get("sku"):
#              print("[DEBUG][STATE] Global override -> forcing stage RESERVE")
#              session["memory"]["stage"] = STAGES["RESERVE"]
#              if meta.get("sku"):
#                  session["memory"]["selection_state"]["product_id"] = meta["sku"]
             
#              # Immediately save and ask for store
#              await save_session(session_id, session)
#              return {
#                 "session_id": session_id,
#                 "results": {
#                     "message": "Sure! Which store would you like to reserve this at?"
#                 },
#                 "next_stage": STAGES["RESERVE"],
#             }
            
    
#     # ================================
#     # 🔒 HARD RESERVE FLOW (FINAL FIX)
#     # ================================
#     if session["memory"]["stage"] == STAGES["RESERVE"]:
#         reservation = session["memory"]["reservation"]
#         selection = session["memory"]["selection_state"]

#         # ---- guards ----
#         if not user_id:
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Please login to reserve items."},
#                 "next_stage": STAGES["RECOMMEND"],
#             }

#         if not selection.get("product_id"):
#             session["memory"]["stage"] = STAGES["RECOMMEND"]
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Please select a product again."},
#                 "next_stage": STAGES["RECOMMEND"],
#             }

#         # ---- ask steps ----
#         if not reservation.get("store_id"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "Which store would you like to reserve this at?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         if not reservation.get("date"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "What date would you like to visit the store?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         if not reservation.get("time"):
#             await save_session(session_id, session)
#             return {
#                 "session_id": session_id,
#                 "results": {"message": "What time should I reserve it for?"},
#                 "next_stage": STAGES["RESERVE"],
#             }

#         # ================================
#         # 🔒 INVENTORY CHECK + INSERT (SAME TX)
#         # ================================
#         async with AsyncSessionLocal() as db:
#             result = await db.execute(
#                 text("""
#                     SELECT stock, reserved
#                     FROM inventory
#                     WHERE product_id = :pid AND store_id = :sid
#                     FOR UPDATE
#                 """),
#                 {
#                     "pid": selection["product_id"],
#                     "sid": reservation["store_id"],
#                 }
#             )
#             row = result.fetchone()

#             if not row or (row.stock - row.reserved) <= 0:
#                 session["memory"]["stage"] = STAGES["AVAILABILITY"]
#                 await save_session(session_id, session)
#                 return {
#                     "session_id": session_id,
#                     "results": {"message": "❌ Sorry, this item just went out of stock."},
#                     "next_stage": STAGES["AVAILABILITY"],
#                 }

#             await db_crud.create_reservation(
#                 db=db,
#                 user_id=user_id,
#                 product_id=selection["product_id"],
#                 store_id=reservation["store_id"],
#                 date=reservation["date"],
#                 time=reservation["time"],
#             )

#         # ================================
#         # 🔒 LOCK STATE AFTER SUCCESS
#         # ================================
#         session["memory"]["selection_state"]["reserved"] = True
#         session["memory"]["stage"] = STAGES["CART"]
#         session["memory"]["reservation"] = {
#             "store_id": None,
#             "date": None,
#             "time": None,
#         }

#         await save_session(session_id, session)

#         return {
#             "session_id": session_id,
#             "results": {
#                 "message": (
#                     f"✅ Reserved at {reservation['store_id']} on "
#                     f"{reservation['date']} at {reservation['time']}."
#                 )
#             },
#             "next_stage": STAGES["CART"],
#         }


#         # await save_session(session_id, session)
#         # return final



    
    
# # ======================================================
#     # STEP 3: HARD PLAN OVERRIDE — DO NOT TRUST LLM PLAN
#     # ======================================================

#     stage = session["memory"].get("stage", STAGES["RECOMMEND"])
#     user_text_lower = (incoming_text or "").lower()

#     # 🔴 FIX 2 START: GLOBAL "ADD TO CART" TRIGGER
#     # This runs BEFORE checking the stage. It forces the Cart Agent to run 
#     # if the user says "add to cart", even if the LLM didn't plan for it.
#     if any(x in user_text_lower for x in ["add to cart", "buy this", "add this", "add it"]):
#         plan = ["cart_agent"]
#         meta["add"] = "product_id" # <--- Critical: Unlocks the CartAgentNode gate
        
#         # Ensure we know WHICH product to add
#         if session["memory"]["selection_state"].get("product_id"):
#             meta["sku"] = session["memory"]["selection_state"]["product_id"]
        
#         print(f"[DEBUG] Global override triggered: Adding {meta.get('sku')} to cart.")

#     # 🔴 ELSE: Run normal stage logic
#     elif stage == STAGES["RECOMMEND"]:
#         plan = ["rec_agent"]

#     elif stage == STAGES["PRODUCT_DETAILS"]:
#         # 🩹 FIX 1: Allow inventory check if user explicitly asks
#         if "inventory_agent" in plan or meta.get("check_availability") or any(x in user_text_lower for x in ["stock", "availabl", "reserve"]):
#              plan = ["inventory_agent"]
#         else:
#              plan = []  # no agent, just show details

#     elif stage == STAGES["AVAILABILITY"]:
#         plan = ["inventory_agent"]

#     elif stage == STAGES["RESERVE"]:
#         plan = [] 

#     elif stage == STAGES["CART"]:
#         plan = ["cart_agent"]

#     elif stage == STAGES["CHECKOUT"]:
#         plan = ["payment_agent"]

#     elif stage == STAGES["PAYMENT"]:
#         plan = []

#     elif stage == STAGES["ORDER_CONFIRMED"]:
#         plan = []
        
#     # 🚫 FIX 3 — NEVER re-run inventory after reservation
#     if session["memory"]["selection_state"].get("reserved") is True:
#         plan = [p for p in plan if p != "inventory_agent"]



#     # 🔥 HARD STOP PAYMENT AGENT DURING EXPLORATION
#     # PaymentAgent should NEVER run unless we are explicitly in checkout/payment stage
# # 🔒 HARD BLOCK checkout-related agents unless explicitly in CHECKOUT or PAYMENT
#     if session["memory"]["stage"] not in (STAGES["CHECKOUT"], STAGES["PAYMENT"]):
#         plan = [
#             p for p in plan
#             if p not in ("payment_agent", "loyalty_agent", "order_agent")
#         ]



#     if not plan and intent == "recommend":
#         plan = ["rec_agent"]
#     elif not plan and intent == "buy":
#         plan = ["rec_agent"]
#     elif not plan and intent == "postpurchase":
#         plan = ["order_agent", "postpurchase_agent"]


#     required_for_checkout = []
#     missing_required = []

#     # Only enforce checkout requirements during checkout/payment
#     if next_stage in ("checkout", "payment", "confirm"):
#         required_for_checkout = ["size", "fit", "fulfillment"]
#         missing_required = [k for k in required_for_checkout if not slots.get(k)]


# # Only block payment_agent if the user is NOT ready_to_buy.
# # If ready_to_buy is true, let PaymentAgentNode handle missing slots with "not_ready" status.
#     if "payment_agent" in plan and not ready_to_buy:
#         plan = [p for p in plan if p != "payment_agent"]
        

#     meta = intent_out.get("meta") or {}
#     selection_state = session["memory"].get("selection_state", {})
#     # ================================
#     # STATE TRANSITION: RECOMMEND → PRODUCT_DETAILS
#     # ================================
#     if meta.get("confirm_selection") and meta.get("sku"):
#         session["memory"]["selection_state"]["product_id"] = meta["sku"]
#         session["memory"]["stage"] = STAGES["PRODUCT_DETAILS"]
        
#     user_text_lower = (incoming_text or "").lower()

#     # ================================
#     # STATE TRANSITION: PRODUCT_DETAILS → AVAILABILITY
#     # ================================
#     if session["memory"]["stage"] == STAGES["PRODUCT_DETAILS"]:
#         if any(x in user_text_lower for x in ["check", "availability", "stock", "yes"]):
#             session["memory"]["stage"] = STAGES["AVAILABILITY"]
    
#     # 🚫 Block checkout if product is out of stock
#     if selection_state.get("out_of_stock") is True:
#         plan = [p for p in plan if p != "payment_agent"]
#         ready_to_buy = False


#     # 🔒 FORCE INVENTORY ONLY WHEN USER CONFIRMS AVAILABILITY CHECK
# # 🔒 FORCE INVENTORY ONLY WHEN USER EXPLICITLY ASKS
#     if (
#         meta.get("check_availability") is True
#         and (meta.get("sku") or selection_state.get("product_id"))
#     ):

#         selection_state["product_id"] = meta.get("sku") or selection_state.get("product_id")
#         selection_state["selected_attributes"] = {}
#         session["memory"]["selection_state"] = selection_state

#         plan = ["inventory_agent"]
#         next_stage = "availability"
#         ready_to_buy = False





#     from difflib import get_close_matches
#     validated_plan = []
#     missing_nodes = []
#     for nid in plan:
#         if nid in g.nodes:
#             validated_plan.append(nid)
#             continue
#         matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
#         if matches:
#             validated_plan.append(matches[0])
#         else:
#             lname = nid.lower()
#             mapped = None
#             if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
#                 mapped = "rec_agent"
#             elif any(tok in lname for tok in ("inventory","stock","availability")):
#                 mapped = "inventory_agent"
#             elif any(tok in lname for tok in ("cart","basket","add to cart","add2cart","add")):
#                 mapped = "cart_agent"
#             elif any(tok in lname for tok in ("pay","payment","checkout","order")):
#                 mapped = "payment_agent"
#             if mapped and mapped in g.nodes:
#                 validated_plan.append(mapped)
#             else:
#                 missing_nodes.append(nid)

#         for node_id in validated_plan:
#                 res = await g.nodes[node_id].run(ctx)
#                 ctx["node_outputs"][node_id] = res.output

#                 # 🛑 NEW: STOCK CHECK GATEKEEPER
#                 # If any agent (Cart or Inventory) reports 'out_of_stock', 
#                 # we MUST stop the loop immediately so payment_agent NEVER runs.
#                 if isinstance(res.output, dict) and res.output.get("out_of_stock"):
#                     # 1. Update session memory to reflect the stock failure
#                     session["memory"]["stage"] = STAGES["AVAILABILITY"]
#                     session["memory"]["selection_state"]["out_of_stock"] = True
                    
#                     # 2. Build the early failure response
#                     final["results"]["message"] = res.output.get("message")
#                     final["results"]["out_of_stock"] = True
#                     if res.output.get("alternatives"):
#                         final["results"]["items"] = res.output.get("alternatives")
                    
#                     # 3. Save and Exit the entire run_master function early
#                     await save_session(session_id, session)
#                     return final
#                 try:
#                     print("[DEBUG] node_outputs keys:", list(ctx["node_outputs"].keys()))
#                     print("[DEBUG] payment_agent output:", json.dumps(ctx["node_outputs"].get("payment_agent"), default=str))
#                     print("[DEBUG] loyalty_agent output:", json.dumps(ctx["node_outputs"].get("loyalty_agent"), default=str))

#             # If payment_agent returned a pending_payment status, log the intent id
#                     pa = ctx["node_outputs"].get("payment_agent") or {}
#                     if isinstance(pa, dict) and pa.get("status") in ("pending_payment", "pending"):
#                         pid = pa.get("payment_intent_id") or (pa.get("meta") or {}).get("payment_intent_id")
#                         print(f"[DEBUG] payment intent created: {pid} final_amount={pa.get('amount') or pa.get('final_amount')}")
#                 except Exception:
#                     print("[DEBUG] failed to dump node_outputs debug info")
#                     traceback.print_exc()
        




#     if isinstance(meta, dict):
#         profile_patch = meta.get("profile") or {}
#         if profile_patch and user_id:
#             await save_user_profile(user_id, profile_patch)
#             session["memory"].setdefault("profile", {}).update(profile_patch)
#     slot_patch = {
#     k: v for k, v in (slots or {}).items()
#     if v not in (None, "", [])
#     and not (
#         next_stage in ("recommend", "validate", "availability")
#         and k in ("size", "fit", "color_preference")
#     )
# }
#     if slot_patch and user_id:
#         await save_user_profile(user_id, slot_patch)
#         session["memory"].setdefault("profile", {}).update(slot_patch)
#     # ================================
#     # CAPTURE PRODUCT-SPECIFIC ATTRIBUTES
#     # ================================
#     selection_state = session["memory"].get("selection_state", {})
    
#     # ♻️ Clear out-of-stock flag if user selects a new product
#     if meta.get("sku") and meta.get("sku") != selection_state.get("product_id"):
#         selection_state.pop("out_of_stock", None)
#         selection_state["product_id"] = meta.get("sku")
#         session["memory"]["selection_state"] = selection_state

#     active_pid = selection_state.get("product_id")

#     if active_pid:
#         selected_attrs = selection_state.setdefault("selected_attributes", {})

#         for k, v in (slots or {}).items():
#             if v not in (None, "", []):
#                 selected_attrs[k] = v

#         session["memory"]["selection_state"] = selection_state


#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     recs = []
#     active_product = None
#     missing_attrs = None

#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         selection_state = session["memory"].get("selection_state", {})
#         active_pid = selection_state.get("product_id")
#         selected_attrs = selection_state.get("selected_attributes", {})

#     active_product = None
#     for p in recs:
#         if p.get("product_id") == active_pid:
#             active_product = p
#             break

#     # 🔁 FALLBACK TO DB IF NOT IN CURRENT RECS
#     if not active_product and active_pid:
#         active_product = await rec_agent.get_product_by_sku(active_pid)

# # ================================
#     # STEP B: SHOW PRODUCT DETAILS (READ-ONLY MODE)
#     # ================================
#     meta = intent_out.get("meta") or {}

#     if active_product and meta.get("show_product_details") is True:
#         # 1. Populate the detailed object
#         final["results"]["product_details"] = {
#             "product_id": active_product.get("product_id"),
#             "name": active_product.get("name"),
#             "price": float(active_product.get("price", 0)),
#             "category": active_product.get("category"),
#             "description": active_product.get("description"),
#             "attributes": active_product.get("attributes", {}),
#             "images": active_product.get("images", []),
#             "complements": active_product.get("complements", []),
#         }

#         # 🔴 FIX START: POPULATE 'items' ARRAY
#         # The frontend needs this list to render the product card image!
#         final["results"]["items"] = [{
#             "product_id": active_product.get("product_id"),
#             "name": active_product.get("name"),
#             "price": float(active_product.get("price", 0)),
#             "image": (active_product.get("images") or [None])[0],
#             "attributes": active_product.get("attributes", {}),
#             "complements": active_product.get("complements", [])
#         }]
#         # 🔴 FIX END

#         final["results"]["message"] = (
#             f"{active_product.get('name')} is priced at ₹{int(active_product.get('price', 0))}. "
#             f"{active_product.get('description') or ''}"
#         )

#         final["results"]["ask"] = [
#             "Would you like me to check availability in nearby stores?"
#         ]

#         await save_session(session_id, session)
#         return final
#     user_text_lower = (incoming_text or "").lower()
    
    



# # 1. HANDLE INVENTORY
#     if "inventory_agent" in outs:
#         inv = outs["inventory_agent"]
#         stores = inv.get("available_stores", [])
#         alternatives = inv.get("alternatives", [])

#         # 🚫 HARD STOP: out of stock -> Show Alternatives
#         if not stores:
#             final["results"]["out_of_stock"] = True
            
#             # Construct message
#             msg = (
#                 "I'm sorry, this item is currently out of stock. "
#                 "✅ I've enabled a notification for you when it returns!\n\n"
#                 "I can show you other options if you'd like."
#             )
            
#             if alternatives:
#                 msg += "In the meantime, here are some similar items you might like:"
#                 # Normalize alternatives for the frontend 'items' array
#                 final["results"]["items"] = [{
#                     "product_id": p.get("product_id"),
#                     "name": p.get("name"),
#                     "price": float(p.get("price", 0)),
#                     "image": (p.get("images") or [None])[0],
#                     "attributes": p.get("attributes", {})
#                 } for p in alternatives]
            
#             final["results"]["message"] = msg
            
#             session["memory"]["selection_state"]["out_of_stock"] = True
#             await save_session(session_id, session)
#             return final

#         # Success Case
#         final["results"]["stores"] = stores
#         final["results"]["ask"] = [
#             "Would you like to reserve it in store to try, or **add to cart**?"
#         ]
#         final["results"]["force_action"] = "fulfillment_choice"
#         final["next_stage"] = "availability"
#         final["ready_to_buy"] = False

#         # ✅ STATE TRANSITION: AVAILABILITY → CART / RESERVE
#         user_text_lower = (incoming_text or "").lower()
        
        
#         if (
#             "reserve" in user_text_lower
#             and session["memory"]["stage"] in (
#                 STAGES["PRODUCT_DETAILS"],
#                 STAGES["AVAILABILITY"],
#             )
#         ):
#             print("[DEBUG][STATE] forcing stage -> RESERVE")

#             session["memory"]["stage"] = STAGES["RESERVE"]
#             await save_session(session_id, session)

#             # 🔒 IMMEDIATELY HAND CONTROL TO RESERVE FLOW
#             return {
#                 "session_id": session_id,
#                 "results": {
#                     "message": "Sure — which store would you like to reserve this at?"
#                 },
#                 "next_stage": STAGES["RESERVE"],
#             }



#         elif any(x in user_text_lower for x in ["add", "cart"]):
#             session["memory"]["stage"] = STAGES["CART"]

#         session["memory"]["selection_state"]["inventory_checked"] = True
#         await save_session(session_id, session)
#         return final

#     print(
#         "[DEBUG][RESERVE] entered",
#         "stage=", session["memory"]["stage"],
#         "reservation=", session["memory"]["reservation"]
#     )







#     if "cart_agent" in outs:
        
#                 # ================================
#         # CHECKOUT FLOW (LOCKED)
#         # ================================
#         if session["memory"]["stage"] == STAGES["CHECKOUT"]:
#             cart = outs.get("cart_agent", {}).get("cart")

#             if not cart or not cart.get("items"):
#                 final["results"]["message"] = "Your cart is empty. Would you like me to add something first?"
#                 await save_session(session_id, session)
#                 return final

#             # Fetch loyalty info
#             async with AsyncSessionLocal() as db:
#                 loyalty = await db_crud.get_user_loyalty(db, user_id)

#             final["results"]["cart"] = cart
#             final["results"]["loyalty"] = loyalty

#             final["results"]["message"] = (
#                 f"Here’s your cart summary:\n"
#                 f"- Items: {len(cart['items'])}\n"
#                 f"- Subtotal: ₹{int(cart['subtotal'])}\n\n"
#                 f"You have {loyalty['points']} loyalty points.\n"
#                 f"Would you like to redeem them for this order?"
#             )

#             await save_session(session_id, session)
#             return final

#         user_text_lower = (incoming_text or "").lower()


    
    
# # ================================
#     # STATE TRANSITION: CART → CHECKOUT
#     # ================================
#     if "checkout" in user_text_lower:
#         session["memory"]["stage"] = STAGES["CHECKOUT"]

#         # 🩹 FIX: Check if cart_agent exists. If not, fetch from DB manually.
#         if "cart_agent" in outs:
#             final["results"]["cart"] = outs["cart_agent"].get("cart")
#             ca_msg = outs["cart_agent"].get("message")
#             if ca_msg:
#                 final["results"]["cart_message"] = ca_msg
#         else:
#             # Fallback: Fetch cart summary from DB so frontend doesn't crash
#             channel = (session_id.split(":")[-1] if ":" in session_id else "web") or "web"
#             if user_id:
#                 # We need to import this if it's not available in local scope, 
#                 # but 'cart_agent' module is imported at top of file
#                 summary = await cart_agent.get_cart_summary(user_id, channel)
#                 final["results"]["cart"] = summary

#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]

#     if "order_agent" in outs:
#         final["results"]["orders"] = outs["order_agent"].get("orders", [])

#     items = []
#     for p in recs:
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#             "complements": p.get("complements", [])
#         })
#     if items:
#         final["results"]["items"] = items
#     if "loyalty_agent" in outs:
#         final["results"]["loyalty"] = outs["loyalty_agent"]
        
#     if "fulfillment_agent" in outs:
#         final["results"]["fulfillment"] = outs["fulfillment_agent"]
#     if "postpurchase_agent" in outs:
#         final["results"]["postpurchase"] = outs["postpurchase_agent"]

#     def _merge_msg_and_questions(msg: Optional[str], qs: List[str]) -> str:
#         base = (msg or "").strip()
#         if not qs:
#             return base or "How can I help you find the right piece today?"

#         # Normalize for comparison (case-insensitive, ignore punctuation)
#         def _norm(s: str) -> str:
#             return s.strip().rstrip(" ?!.").lower()

#         base_norm = _norm(base) if base else ""
#         unique_q = None

#         for q in qs:
#             q = (q or "").strip()
#             if not q:
#                 continue
#             # If this question is already present inside the base message, skip
#             if base and _norm(q) in base_norm:
#                 continue
#             unique_q = q
#             break

#         # If all questions were duplicates of what's already in message
#         if not unique_q:
#             return base or "How can I help you find the right piece today?"

#         if base:
#             # base already typically ends with ? or .
#             return base + " " + unique_q
#         else:
#             return unique_q

#     def _normalize_order_result(order_obj):
#         if not isinstance(order_obj, dict):
#             return {
#                 "status": None,
#                 "success": False,
#                 "order_id": None,
#                 "message": None,
#                 "error": None,
#             }
#         status = order_obj.get("status")
#         if status is None and "success" in order_obj:
#             status = "success" if bool(order_obj.get("success")) else "error"
#         order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
#         message = order_obj.get("message")
#         error = order_obj.get("error")
#         return {
#             "status": status,
#             "success": bool(order_obj.get("success") or (status == "success")),
#             "order_id": order_id,
#             "message": message,
#             "error": error,
#             "raw": order_obj,
#         }

#     order = final["results"].get("order", {})
#     order_norm = _normalize_order_result(order)
#     status = order.get("status") if isinstance(order, dict) else None

#     def _merge_msg_and_questions(msg: Optional[str], qs: List[str]) -> str:
#         base = (msg or "").strip()
#         if not qs:
#             return base or "How can I help you find the right piece today?"

#         # Normalize for comparison (case-insensitive, ignore punctuation)
#         def _norm(s: str) -> str:
#             return s.strip().rstrip(" ?!.").lower()

#         base_norm = _norm(base) if base else ""
#         unique_q = None

#         for q in qs:
#             q = (q or "").strip()
#             if not q:
#                 continue
#             # If this question is already present inside the base message, skip
#             if base and _norm(q) in base_norm:
#                 continue
#             unique_q = q
#             break

#         # If all questions were duplicates of what's already in message
#         if not unique_q:
#             return base or "How can I help you find the right piece today?"

#         if base:
#             # base already typically ends with ? or .
#             return base + " " + unique_q
#         else:
#             return unique_q

#     # ================================
#     # Decide final user-facing message
#     # ================================
    
# # 🔴 FIX 3 START: PRIORITY MESSAGE OVERRIDE
#     # If the Cart Agent actually ran and returned a message (e.g. "Added 1 item"), 
#     # we use THAT message instead of the LLM's hallucination.
#     if "cart_agent" in outs and outs["cart_agent"].get("message"):
#         final["results"]["message"] = outs["cart_agent"]["message"]
        
#     # Same for Inventory (e.g. "Out of Stock")
#     elif "inventory_agent" in outs and outs["inventory_agent"].get("message"):
#         final["results"]["message"] = outs["inventory_agent"]["message"]
#     # 🔴 FIX 3 END
#     if order:
#         # 1) Intermediate payment states from PaymentAgentNode
#         if status in ("needs_loyalty_decision", "not_ready", "payment_cancelled"):
#             # Just surface the PaymentAgentNode message directly
#             final["results"]["message"] = order.get("message") or final["results"].get("message")

#         # 2) QR pending (UPI QR generated, waiting for user to pay)
#         #    ⚠️ UPDATED: Replaced "awaiting_payment_confirmation" with "pending_payment" logic
#         elif status in ("pending", "pending_payment", "awaiting_payment_confirmation"):
#             final_msg = order.get("message") or "I've generated a payment QR for you. Please scan it and then confirm."
#             final["results"]["message"] = final_msg

#         # 3) Final success / error (e.g. from /payment/confirm or future flows)
#         elif order_norm["success"] or order_norm["status"] in ("success", "error"):
#             err = order_norm.get("error") or (order.get("error"))
#             agent_msg = order.get("message") or order.get("details")
#             if agent_msg:
#                 final_msg = agent_msg
#             elif err == "out_of_stock":
#                 sku = (order.get("meta") or {}).get("sku")
#                 final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
#             else:
#                 final_msg = f"Order failed: {err or 'unknown_error'}."
#             final["results"]["message"] = final_msg

#         # 4) Order object exists but status is something unexpected → fall back to LLM
#         else:
#             llm_message = intent_out.get("message")
#             llm_ask = intent_out.get("ask") or []
#             if llm_message or llm_ask:
#                 final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
#             else:
#                 if intent == "recommend" and items:
#                     final["results"]["message"] = (
#                         f"I found {len(items)} items — here are the top matches. What occasion are you shopping for?"
#                     )
#                 elif intent == "other":
#                     txt = ctx.get("incoming_text", "") or ""
#                     mem = session.get("memory", {})
#                     if "name" in mem and "what is my name" in txt.lower():
#                         final["results"]["message"] = f"Your name is {mem['name']}."
#                     else:
#                         final["results"]["message"] = (
#                             "Hello! I can help you find and buy products. What occasion are you shopping for?"
#                         )
#                 else:
#                     final["results"]["message"] = "Here are the results. Would you like casual or office wear?"
#     else:
#         # No payment/order object → normal LLM-driven message
#         llm_message = intent_out.get("message")
#         llm_ask = intent_out.get("ask") or []
#         if llm_message or llm_ask:
#             final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
#         else:
#             if intent == "recommend" and items:
#                 final["results"]["message"] = (
#                     f"I found {len(items)} items — here are the top matches. What occasion are you shopping for?"
#                 )
#             elif intent == "other":
#                 txt = ctx.get("incoming_text", "") or ""
#                 mem = session.get("memory", {})
#                 if "name" in mem and "what is my name" in txt.lower():
#                     final["results"]["message"] = f"Your name is {mem['name']}."
#                 else:
#                     final["results"]["message"] = (
#                         "Hello! I can help you find and buy products. What occasion are you shopping for?"
#                     )
#             else:
#                 final["results"]["message"] = "Here are the results. Would you like casual or office wear?"

#     try:
#         print(f"[MASTER] final message -> {final['results'].get('message')}")
#     except Exception:
#         pass

#     session.setdefault("history", []).append({
#         "incoming": incoming_text,
#         "intent": intent,
#         "results": final["results"],
#         "slots": slots,
#         "next_stage": next_stage
#     })
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(incoming_text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)
#     if user_id:
#         await set_active_session_for_user(user_id, session_id)
#     final["llm_notes"] = intent_out.get("notes")
#     final["slots"] = slots
#     # ================================
#     # STATE TRANSITION: CHECKOUT → PAYMENT
#     # ================================
#     if slots.get("confirm_payment") is True:
#         session["memory"]["stage"] = STAGES["PAYMENT"]
#     final["next_stage"] = session["memory"]["stage"]
#     final["ready_to_buy"] = ready_to_buy
#     return final


