# backend/agents/orchestrator_fallback.py
from . import rec_agent, inventory_agent, payment_agent
from typing import Dict, Any

async def run_orchestrator(session_id: str, text: str, user_meta: Dict[str, Any] = None):
    text_l = text.lower()
    if any(w in text_l for w in ["buy","order","checkout"]):
        intent = "buy"
    elif any(w in text_l for w in ["recommend","suggest","need","looking for","show"]):
        intent = "recommend"
    else:
        intent = "recommend"

    if intent == "recommend":
        recs = rec_agent.simple_keyword_recommend(text)
        inv = [inventory_agent.check_stock(p["product_id"]) for p in recs]
        return {
            "session_id": session_id,
            "intent": intent,
            "recs": recs,
            "inventory": inv,
            "text": f"I found {len(recs)} items for you."
        }

    if intent == "buy":
        recs = rec_agent.simple_keyword_recommend(text, top_k=1)
        if not recs:
            return {"error":"no products found"}
        p = recs[0]
        ok = inventory_agent.reserve_stock(p["product_id"])
        if not ok:
            return {"error":"out_of_stock"}
        payment = payment_agent.process_payment_mock(user_meta.get("user_id","anonymous"), float(p["price"]))
        return {"order":{"product":p,"payment":payment},"text":"Order placed (mock)"}
