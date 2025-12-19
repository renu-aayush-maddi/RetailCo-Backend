from typing import Dict, Any
from backend.agents.base import Node, NodeResult
from .availability_agent import check_product_availability

class AvailabilityNode(Node):
    def __init__(self, id: str = "availability_agent"):
        super().__init__(id)

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        selection = ctx.get("memory", {}).get("selection_state", {})
        product_id = selection.get("product_id")

        if not product_id:
            return NodeResult({"stores": []})

        data = await check_product_availability(product_id)
        return NodeResult(data)
