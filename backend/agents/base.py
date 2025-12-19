from typing import Dict, Any

class NodeResult:
    def __init__(self, output: Dict[str, Any]):
        self.output = output


class Node:
    def __init__(self, id: str):
        self.id = id

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        return NodeResult({})
