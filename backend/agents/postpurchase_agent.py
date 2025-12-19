# backend/agents/postpurchase_agent.py
import random
from backend.db import AsyncSessionLocal
from backend import crud

async def track_order(user_id: str, order_id: str = None):
    async with AsyncSessionLocal() as db:
        if order_id:
            order = await crud.get_order_by_id(db, order_id)
        else:
            order = await crud.get_latest_order_for_user(db, user_id)
    
    if not order:
        return {"found": False, "message": "You don't have any recent orders to track."}

    # MOCK LOGISTIC STATUS
    statuses = ["Order Placed", "Packed", "Shipped", "Out for Delivery", "Delivered"]
    # Pick a random status based on order ID hash to be consistent but fake
    idx = hash(order.order_id) % len(statuses)
    current_status = statuses[idx]
    
    tracking_link = f"https://logistics.retailco.com/track/{order.order_id}"
    
    return {
        "found": True,
        "order_id": order.order_id,
        "status": current_status,
        "tracking_link": tracking_link,
        "items_count": len(order.items) if order.items else 0,
        "total": float(order.total_amount)
    }

async def process_return(user_id: str, reason: str):
    async with AsyncSessionLocal() as db:
        # Auto-select latest order for the demo
        order = await crud.get_latest_order_for_user(db, user_id)
        if not order:
            return {"success": False, "message": "No order found to return."}
        
        # Assume returning the first item in the order
        first_item = order.items[0] if order.items else {}
        pid = first_item.get("product_id", "unknown")
        
        ret_id = await crud.create_return_request(db, user_id, order.order_id, pid, reason)
        
    return {
        "success": True,
        "return_id": ret_id,
        "message": f"Return initiated for {pid}. Refund of ₹{order.total_amount} will be processed to your source account within 5 days."
    }

async def submit_feedback(user_id: str, rating: int, comment: str):
    async with AsyncSessionLocal() as db:
        order = await crud.get_latest_order_for_user(db, user_id)
        oid = order.order_id if order else "general"
        await crud.create_feedback(db, user_id, oid, rating, comment)
    
    return {"success": True, "message": "Thank you! Your feedback helps us improve."}