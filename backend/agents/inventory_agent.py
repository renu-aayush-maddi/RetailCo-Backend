from typing import Dict, Any
from backend.db import AsyncSessionLocal
from backend import crud
from backend.agents.base import Node, NodeResult


class RealtimeInventoryNode(Node):
    def __init__(self, id: str = "realtime_inventory_agent"):
        super().__init__(id)

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        selection_state = (ctx.get("memory") or {}).get("selection_state", {})
        product_id = selection_state.get("product_id")

        if not product_id:
            return NodeResult({"available_stores": []})

        async with AsyncSessionLocal() as session:
            rows = await crud.get_inventory_by_product(session, product_id)

        stores = []
        for r in rows:
            available = max((r.stock or 0) - (r.reserved or 0), 0)
            if available > 0:
                stores.append({
                    "store_id": r.store_id,
                    "location": r.location,
                    "available_qty": available
                })

        return NodeResult({
            "product_id": product_id,
            "available_stores": stores
        })
