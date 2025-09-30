# # backend/agents/master_graph.py
# """
# Lightweight AgentGraph runtime with Redis-backed memory and LLM node.
# Uses OpenAI by default; switch to GROQ via USE_GROQ env var.
# Wires rec -> inventory -> payment nodes and persists session memory.
# """

# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1","true","yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# from . import rec_agent, inventory_agent, payment_agent

# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output

# class Node:
#     def __init__(self, id: str):
#         self.id = id
#         self.next_nodes: List[str] = []

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})

# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node

#     def add_edge(self, from_id: str, to_id: str):
#         if from_id not in self.nodes or to_id not in self.nodes:
#             raise ValueError("node id missing")
#         self.nodes[from_id].next_nodes.append(to_id)

#     async def run(self, start_node_id: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
#         if start_node_id not in self.nodes:
#             raise ValueError("start node missing")
#         visited = []
#         queue = [start_node_id]
#         while queue:
#             nid = queue.pop(0)
#             node = self.nodes[nid]
#             visited.append(nid)
#             try:
#                 res = await node.run(ctx)
#                 ctx.setdefault("node_outputs", {})[nid] = res.output
#             except Exception as e:
#                 ctx.setdefault("node_outputs", {})[nid] = {"error": str(e)}
#             for nxt in node.next_nodes:
#                 if nxt not in visited and nxt not in queue:
#                     queue.append(nxt)
#         return ctx

# SESSION_PREFIX = "session:"

# async def load_session(session_id: str) -> Dict[str, Any]:
#     key = SESSION_PREFIX + session_id
#     raw = await redis.get(key)
#     if not raw:
#         return {"session_id": session_id, "memory": {}, "history": []}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {"session_id": session_id, "memory": {}, "history": []}

# async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60*60*24):
#     key = SESSION_PREFIX + session_id
#     await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)

# class LLMAgentNode(Node):
#     def __init__(self, id: str, system_prompt: str, timeout: int = 15):
#         super().__init__(id)
#         self.system_prompt = system_prompt
#         self.timeout = timeout

#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
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
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {
#             "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
#             "input": prompt,
#             "temperature": 0.0
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         prompt = f"{self.system_prompt}\n\nSessionMemory:{json.dumps(session_memory)}\nUser:{user_text}\n\nReturn JSON only."

#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             out = json.dumps({"intent":"recommend","notes":"no-llm-key"})

#         parsed = {}
#         try:
#             parsed = json.loads(out)
#         except Exception:
#             import re
#             m = re.search(r"(\{.*\})", out, re.S)
#             if m:
#                 try:
#                     parsed = json.loads(m.group(1))
#                 except Exception:
#                     parsed = {"raw": out}
#             else:
#                 parsed = {"raw": out}

#         return NodeResult(parsed)

# class RecAgentNode(Node):
#     def __init__(self, id: str = "rec_agent", top_k: int = 3):
#         super().__init__(id)
#         self.top_k = top_k

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         recs = rec_agent.simple_keyword_recommend(user_text, top_k=self.top_k)
#         return NodeResult({"recs": recs})

# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         if "rec_agent" in nodouts:
#             recs = nodouts["rec_agent"].get("recs", [])
#         else:
#             recs = ctx.get("recs") or []
#         invs = []
#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock(pid, self.store_id)
#             invs.append({"product_id": pid, "stock": inv.get("stock",0), "reserved": inv.get("reserved",0)})
#         return NodeResult({"inventory": invs})
# # --- replace this block in backend/agents/master_graph.py ---

# class PaymentAgentNode(Node):
#     def __init__(self, id: str = "payment_agent"):
#         super().__init__(id)

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         """
#         New behavior:
#          - Use DB-backed reserve + create order (process_checkout_db)
#          - If DB unavailable, fall back to local reservation + mock payment
#         """
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         if not recs:
#             return NodeResult({"error": "no_recommendation_to_buy"})
#         chosen = recs[0]
#         product_id = chosen.get("product_id")
#         price = float(chosen.get("price", 0))

#         # Try DB-backed checkout
#         try:
#             # import process_checkout_db from payment_agent
#             from . import payment_agent as payment_agent_module
#             # in PaymentAgentNode.run before calling process_checkout_db
#             print(f"[MASTER] PaymentAgentNode invoked for user={ctx.get('user_id')} product={product_id} price={price}")

#             result = await payment_agent_module.process_checkout_db(ctx.get("user_id", "anonymous"), product_id, price, store_id="S1", qty=1)
#             return NodeResult(result)
#         except Exception as e:
#             # Fallback: try local reservation + mock payment
#             try:
#                 from . import inventory_agent as inv_mod, payment_agent as pay_mod
#                 ok_local = inv_mod.reserve_stock_local(product_id, "S1", 1)
#                 if not ok_local:
#                     return NodeResult({"error": "out_of_stock"})
#                 payment = pay_mod.process_payment_mock(ctx.get("user_id", "anonymous"), price)
#                 order_id = "ORD-" + uuid.uuid4().hex[:8]
#                 return NodeResult({"order_id": order_id, "payment": payment, "product": chosen})
#             except Exception as e2:
#                 return NodeResult({"error": "checkout_failed", "details": str(e2)})

# # class PaymentAgentNode(Node):
# #     def __init__(self, id: str = "payment_agent"):
# #         super().__init__(id)

# #     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
# #         nodouts = ctx.get("node_outputs", {})
# #         recs = nodouts.get("rec_agent", {}).get("recs", [])
# #         if not recs:
# #             return NodeResult({"error":"no_recommendation_to_buy"})
# #         chosen = recs[0]
# #         ok = inventory_agent.reserve_stock(chosen["product_id"])
# #         if not ok:
# #             return NodeResult({"error":"out_of_stock"})
# #         payment = payment_agent.process_payment_mock(ctx.get("user_id","anonymous"), float(chosen.get("price",0)))
# #         order_id = "ORD-" + uuid.uuid4().hex[:8]
# #         return NodeResult({"order_id": order_id, "payment": payment, "product": chosen})

# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
#     session = await load_session(session_id)
#     ctx = {
#         "session_id": session_id,
#         "user_id": (user_meta or {}).get("user_id"),
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")

#     intent_prompt = (
#         "You are a Retail Master Agent. Return JSON: {\"intent\":\"recommend\"|\"buy\"|\"other\",\"plan\":[...],\"notes\":\"optional\"}"
#     )
#     llm_node = LLMAgentNode("llm_intent", system_prompt=intent_prompt)
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")

#     g.add_node(llm_node)
#     g.add_node(rec_node)
#     g.add_node(inv_node)
#     g.add_node(pay_node)

#     g.add_edge("llm_intent", "rec_agent")
#     g.add_edge("rec_agent", "inventory_agent")
#     g.add_edge("inventory_agent", "payment_agent")

#     ctx_after = await g.run("llm_intent", ctx)

#     intent_out = ctx_after.get("node_outputs", {}).get("llm_intent", {})
#     intent = intent_out.get("intent", "recommend") if isinstance(intent_out, dict) else "recommend"

#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outputs = ctx_after.get("node_outputs", {})
#     final["results"]["recommendations"] = outputs.get("rec_agent", {})
#     final["results"]["inventory"] = outputs.get("inventory_agent", {})
#     if intent == "buy":
#         final["results"]["order"] = outputs.get("payment_agent", {})

#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60*60*24*7)

#     final["llm_notes"] = intent_out.get("notes") if isinstance(intent_out, dict) else None
#     return final






# """
# Agentic Orchestration Graph with Redis-backed session memory.
# LLM decides intent + plan, then only the requested agents run.
# """

# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # import agents
# from . import rec_agent, inventory_agent, payment_agent


# # ---------------- Node + Graph base ----------------

# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output


# class Node:
#     def __init__(self, id: str):
#         self.id = id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})


# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node


# # ---------------- Session Memory ----------------

# SESSION_PREFIX = "session:"


# async def load_session(session_id: str) -> Dict[str, Any]:
#     key = SESSION_PREFIX + session_id
#     raw = await redis.get(key)
#     if not raw:
#         return {"session_id": session_id, "memory": {}, "history": []}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {"session_id": session_id, "memory": {}, "history": []}


# async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24):
#     key = SESSION_PREFIX + session_id
#     await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


# # ---------------- Nodes ----------------

# class LLMAgentNode(Node):
#     def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
#         super().__init__(id)
#         self.system_prompt = system_prompt or (
#             "You are a Retail Master Orchestrator.\n"
#             "Return JSON ONLY with fields:\n"
#             "{\n"
#             "  \"intent\": \"recommend\" | \"buy\" | \"other\",\n"
#             "  \"plan\": [list of agent IDs to call, in order],\n"
#             "  \"notes\": \"short reasoning\"\n"
#             "}\n\n"
#             "Examples:\n"
#             "User: hello → {\"intent\":\"other\",\"plan\":[],\"notes\":\"greeting\"}\n"
#             "User: show me jeans → {\"intent\":\"recommend\",\"plan\":[\"rec_agent\",\"inventory_agent\"],\"notes\":\"user wants suggestions\"}\n"
#             "User: buy the first one → {\"intent\":\"buy\",\"plan\":[\"rec_agent\",\"inventory_agent\",\"payment_agent\"],\"notes\":\"user wants to checkout\"}\n"
#         )
#         self.timeout = timeout

#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 400
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]

#     async def call_groq(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {
#             "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
#             "input": prompt,
#             "temperature": 0.0
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         prompt = f"SessionMemory: {json.dumps(session_memory)}\nUser: {user_text}"

#         out = ""
#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             # Fallback: simple rules
#             if any(w in user_text.lower() for w in ["buy", "order", "purchase"]):
#                 out = json.dumps({"intent": "buy", "plan": ["rec_agent", "inventory_agent", "payment_agent"], "notes": "rule-based buy"})
#             elif any(w in user_text.lower() for w in ["recommend", "show", "suggest", "find"]):
#                 out = json.dumps({"intent": "recommend", "plan": ["rec_agent", "inventory_agent"], "notes": "rule-based rec"})
#             elif any(w in user_text.lower() for w in ["hello", "hi", "hey"]):
#                 out = json.dumps({"intent": "other", "plan": [], "notes": "greeting"})
#             else:
#                 out = json.dumps({"intent": "other", "plan": [], "notes": "rule-based fallback"})

#         try:
#             parsed = json.loads(out)
#         except Exception:
#             parsed = {"intent": "other", "plan": [], "notes": "failed to parse", "raw": out}

#         return NodeResult(parsed)


# class RecAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         recs = rec_agent.simple_keyword_recommend(user_text, top_k=3)
#         return NodeResult({"recs": recs})


# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         invs = []
#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock_local(pid, self.store_id)
#             invs.append({"product_id": pid, "stock": inv.get("stock", 0), "reserved": inv.get("reserved", 0)})
#         return NodeResult({"inventory": invs})


# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         if not recs:
#             return NodeResult({"error": "no_recommendation_to_buy"})
#         chosen = recs[0]
#         product_id = chosen.get("product_id")
#         price = float(chosen.get("price", 0))

#         try:
#             result = await payment_agent.process_checkout_db(ctx.get("user_id", "anonymous"), product_id, price, store_id="S1", qty=1)
#             return NodeResult(result)
#         except Exception:
#             return NodeResult({"error": "checkout_failed"})


# # ---------------- Master Runner ----------------

# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
#     session = await load_session(session_id)
#     ctx = {
#         "session_id": session_id,
#         "user_id": (user_meta or {}).get("user_id"),
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")

#     # nodes
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")

#     for n in [llm_node, rec_node, inv_node, pay_node]:
#         g.add_node(n)

#     # run intent node first
#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", [])

#     # run only nodes in plan
#     for node_id in plan:
#         if node_id in g.nodes:
#             res = await g.nodes[node_id].run(ctx)
#             ctx["node_outputs"][node_id] = res.output
            
#         # ---------------- ASSEMBLE FINAL (replace existing assembly logic here) ----------------
#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     # If rec_agent ran, include raw recs
#     recs = []
#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         final["results"]["recommendations"] = {"recs": recs}

#     # If inventory_agent ran, include inventory info
#     if "inventory_agent" in outs:
#         final["results"]["inventory"] = outs["inventory_agent"]

#     # If payment_agent ran, include order/payment info
#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]

#     # Build a user-friendly items array for frontend cards if recommendations exist
#     items = []
#     for p in recs:
#         # normalize product fields to what frontend expects
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             # price may be numeric/str — ensure numeric
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             # use first image if available, convert relative paths to absolute if needed
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#         })
#     if items:
#         final["results"]["items"] = items

#     # Friendly assistant message:
#     if intent == "buy" and final["results"].get("order"):
#         order = final["results"]["order"]
#         if order.get("status") == "success" or order.get("order_id"):
#             final["results"]["message"] = f"Order confirmed — Order ID: {order.get('order_id')}. Payment status: {order.get('payment', {}).get('status', 'unknown')}"
#         else:
#             # show helpful error text
#             final["results"]["message"] = order.get("error", "Could not complete order. Please try again.")
#     elif intent == "recommend" and items:
#         final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
#     elif intent == "other":
#         # keep existing friendly fallback or LLM note
#         final["results"]["message"] = final.get("llm_notes") or "Hello! I can help you find and buy products."
#     else:
#         # generic fallback
#         final["results"]["message"] = final.get("results", {}).get("message") or "Here are the results."

#     # persist session history (existing logic)
#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     final["llm_notes"] = intent_out.get("notes")
#     return final


#     # assemble final
#     # final = {"session_id": session_id, "intent": intent, "results": {}}
#     # outs = ctx["node_outputs"]

#     # if "rec_agent" in outs:
#     #     final["results"]["recommendations"] = outs["rec_agent"]
#     # if "inventory_agent" in outs:
#     #     final["results"]["inventory"] = outs["inventory_agent"]
#     # if "payment_agent" in outs:
#     #     final["results"]["order"] = outs["payment_agent"]
#     # if intent == "other" and not plan:
#     #     final["results"]["message"] = "Hello! I can help you find and buy products."

#     # # update session memory
#     # session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     # mem = session.get("memory", {})
#     # mem.setdefault("recent_queries", []).append(text)
#     # mem["recent_queries"] = mem["recent_queries"][-5:]
#     # session["memory"] = mem
#     # session["last_updated"] = __import__("time").time()
#     # await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     # final["llm_notes"] = intent_out.get("notes")
#     # return final









# # backend/agents/master_graph.py
# """
# Agentic Orchestration Graph with Redis-backed session memory.
# LLM decides intent + plan, then only the requested agents run.
# """

# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # import agents
# from . import rec_agent, inventory_agent, payment_agent


# # ---------------- Node + Graph base ----------------

# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output


# class Node:
#     def __init__(self, id: str):
#         self.id = id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})


# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node


# # ---------------- Session Memory ----------------

# SESSION_PREFIX = "session:"


# async def load_session(session_id: str) -> Dict[str, Any]:
#     key = SESSION_PREFIX + session_id
#     raw = await redis.get(key)
#     if not raw:
#         return {"session_id": session_id, "memory": {}, "history": []}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {"session_id": session_id, "memory": {}, "history": []}


# async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24):
#     key = SESSION_PREFIX + session_id
#     await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


# # ---------------- Nodes ----------------

# class LLMAgentNode(Node):
#     def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
#         super().__init__(id)
#         available_agents = ["rec_agent", "inventory_agent", "payment_agent"]
#         # NOTE: use f-string to interpolate the available_agents list into the prompt
#         self.system_prompt = system_prompt or f"""
#         You are the Retail Master Orchestrator.
#         You MUST respond in JSON only. No explanations, no markdown.
#         AVAILABLE_AGENTS: {available_agents}

#         JSON format:
#         {{
#                 "intent": "recommend" | "buy" | "other",
#                 "plan": [list of agent IDs to call, in order],        // MUST use only IDs from AVAILABLE_AGENTS
#                 "message": "a concise human-friendly reply to show to the user",
#                 "notes": "developer-only short reasoning (optional)",
#                 "meta": {{ ... optional structured details (e.g. rec_query, sku, qty) ... }}
#         }}

# IMPORTANT RULES:
# - Always include "plan" when the user expects data/action. Do not leave plan empty if the user asked to see products, check availability, or buy.
# - If the user asks for product suggestions, 'plan' should include ["rec_agent","inventory_agent"] and meta.rec_query may contain the exact search string or filters.
# - If the user asks to buy/place an order, 'plan' should include ["rec_agent","inventory_agent","payment_agent"] and meta should contain "sku":"P001","qty":1 or similar.
# - Use only agent IDs from AVAILABLE_AGENTS; if you need functionality not in AVAILABLE_AGENTS, return intent:"other" and message asking for clarification.


#         """
#         self.timeout = timeout


#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 400
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]

#     async def call_groq(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {
#             "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
#             "input": prompt,
#             "temperature": 0.0
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         """
#         Fully dynamic LLM-driven intent/plan/message.
#         No static fallbacks. Requires OpenAI or GROQ key.
#         """
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         prompt = (
#             f"SessionMemory: {json.dumps(session_memory)}\n\n"
#             f"User: {user_text}\n\n"
#             "Respond strictly in JSON as specified."
#         )

#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             raise RuntimeError("No LLM provider configured (OPENAI_API_KEY or GROQ_API_KEY required)")

#         parsed = None
#         try:
#             parsed = json.loads(out)
#         except Exception:
#             import re
#             m = re.search(r"(\{.*\})", out, re.S)
#             if m:
#                 try:
#                     parsed = json.loads(m.group(1))
#                 except Exception:
#                     parsed = {"intent": "other", "plan": [], "message": None, "notes": "failed_json_parse", "raw": out}
#             else:
#                 parsed = {"intent": "other", "plan": [], "message": None, "notes": "no_json_found", "raw": out}

#         # Normalize
#         intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
#         plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
#         message = parsed.get("message") if isinstance(parsed, dict) else None
#         notes = parsed.get("notes") if isinstance(parsed, dict) else None
#         meta = parsed.get("meta") if isinstance(parsed, dict) else None

#         normalized = {
#             "intent": intent,
#             "plan": plan,
#             "message": message,
#             "notes": notes,
#             "meta": meta,
#             "raw": out
#         }

#         return NodeResult(normalized)


# # class RecAgentNode(Node):
# #     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
# #         user_text = ctx.get("incoming_text", "")
# #         recs = rec_agent.simple_keyword_recommend(user_text, top_k=3)
# #         return NodeResult({"recs": recs})

# class RecAgentNode(Node):
#     async def run(self, ctx):
#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm_intent = nodouts.get("llm_intent", {}) or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None
#         if meta:
#             recs = rec_agent.recommend_from_meta(meta, top_k=3)
#         else:
#             user_text = ctx.get("incoming_text", "")
#             recs = rec_agent.simple_keyword_recommend(user_text, top_k=3)
#         return NodeResult({"recs": recs})



# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         invs = []
#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock_local(pid, self.store_id)
#             invs.append({"product_id": pid, "stock": inv.get("stock", 0), "reserved": inv.get("reserved", 0)})
#         return NodeResult({"inventory": invs})


# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         if not recs:
#             return NodeResult({"error": "no_recommendation_to_buy"})
#         chosen = recs[0]
#         product_id = chosen.get("product_id")
#         price = float(chosen.get("price", 0))

#         try:
#             result = await payment_agent.process_checkout_db(ctx.get("user_id", "anonymous"), product_id, price, store_id="S1", qty=1)
#             return NodeResult(result)
#         except Exception as e:
#             return NodeResult({"error": "checkout_failed", "details": str(e)})


# # ---------------- Master Runner ----------------

# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
#     session = await load_session(session_id)
#     ctx = {
#         "session_id": session_id,
#         "user_id": (user_meta or {}).get("user_id"),
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")

#     # nodes
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")

#     for n in [llm_node, rec_node, inv_node, pay_node]:
#         g.add_node(n)

#     # run intent node first
#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []

#     # Validate plan
#     validated_plan = [nid for nid in plan if nid in g.nodes]
#     missing_nodes = [nid for nid in plan if nid not in g.nodes]
#     if missing_nodes:
#         print(f"[MASTER] Ignored missing nodes from LLM: {missing_nodes}")

#     # run only nodes in validated plan
#     for node_id in validated_plan:
#         res = await g.nodes[node_id].run(ctx)
#         ctx["node_outputs"][node_id] = res.output

#     # ---------------- ASSEMBLE FINAL ----------------
#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     # If rec_agent ran, include raw recs
#     recs = []
#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         final["results"]["recommendations"] = {"recs": recs}

#     # If inventory_agent ran, include inventory info
#     if "inventory_agent" in outs:
#         final["results"]["inventory"] = outs["inventory_agent"]

#     # If payment_agent ran, include order/payment info
#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]

#     # Build a user-friendly items array
#     items = []
#     for p in recs:
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#         })
#     if items:
#         final["results"]["items"] = items

#     # Prefer explicit LLM message
#     llm_message = intent_out.get("message")
#     if llm_message:
#         final["results"]["message"] = llm_message
#     else:
#         if intent == "buy" and final["results"].get("order"):
#             order = final["results"]["order"]
#             if order.get("status") == "success" or order.get("order_id"):
#                 final["results"]["message"] = f"Order confirmed — Order ID: {order.get('order_id')}. Payment status: {order.get('payment', {}).get('status', 'unknown')}"
#             else:
#                 final["results"]["message"] = order.get("error", "Could not complete order. Please try again.")
#         elif intent == "recommend" and items:
#             final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
#         else:
#             final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."

#     # persist session memory
#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     final["llm_notes"] = intent_out.get("notes")
#     return final





# # backend/agents/master_graph.py
# """
# Agentic Orchestration Graph with Redis-backed session memory.
# LLM decides intent + plan, then only the requested agents run.
# """

# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # import agents
# from . import rec_agent, inventory_agent, payment_agent

# # for order queries
# from backend.db import AsyncSessionLocal
# from backend import crud as db_crud


# # ---------------- Node + Graph base ----------------

# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output


# class Node:
#     def __init__(self, id: str):
#         self.id = id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})


# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node


# # ---------------- Session Memory ----------------

# SESSION_PREFIX = "session:"


# async def load_session(session_id: str) -> Dict[str, Any]:
#     key = SESSION_PREFIX + session_id
#     raw = await redis.get(key)
#     if not raw:
#         return {"session_id": session_id, "memory": {}, "history": []}
#     try:
#         return json.loads(raw)
#     except Exception:
#         return {"session_id": session_id, "memory": {}, "history": []}


# async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24):
#     key = SESSION_PREFIX + session_id
#     await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


# # ---------------- Nodes ----------------

# class LLMAgentNode(Node):
#     def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
#         super().__init__(id)
#         available_agents = ["rec_agent", "inventory_agent", "payment_agent", "order_agent"]
#         self.system_prompt = system_prompt or f"""
# You are the Retail Master Orchestrator. You MUST respond in JSON only. No explanations, no markdown.

# AVAILABLE_AGENTS: {available_agents}

# Strict JSON shape:
# {{
#   "intent": "recommend" | "buy" | "other" | "profile",
#   "plan": [list of agent IDs to call, in order],        // MUST use only IDs from AVAILABLE_AGENTS
#   "message": "a concise human-friendly reply to show the user",
#   "notes": "developer-only short reasoning (optional)",
#   "meta": {{ ... optional structured details (e.g. rec_query, sku, qty, profile) ... }}
# }}

# IMPORTANT RULES:
# - Always include "plan" when the user expects data/action (recommendations, availability checks, buy).
# - If the user asks for product suggestions, 'plan' should include ["rec_agent","inventory_agent"] and meta.rec_query may contain the exact search string or filters.
# - If the user asks to buy/place an order, 'plan' should include ["rec_agent","inventory_agent","payment_agent"] and meta should contain {{"sku":"P001","qty":1}} or similar.
# - Use only agent IDs from AVAILABLE_AGENTS; if you need functionality not listed, return intent:"other" and a clarifying message.

# EXAMPLES:
# 1) User: "show me white shirts for formal occasions"
# {{
#   "intent": "recommend",
#   "plan": ["rec_agent","inventory_agent"],
#   "message": "Great — here are a few white formal shirts I found (I included SKUs). Which would you like to try?",
#   "notes": "recommendation with rec_query",
#   "meta": {{"rec_query":"white formal shirt", "filters":{{"style":"formal"}}}}
# }}

# 2) User: "I want to buy the first one (SKU P001)"
# {{
#   "intent": "buy",
#   "plan": ["rec_agent","inventory_agent","payment_agent"],
#   "message": "I can place the order for SKU P001 — shall I proceed to payment?",
#   "notes": "user asked to checkout specific SKU",
#   "meta": {{"sku":"P001","qty":1}}
# }}

# 3) User: "hi"
# {{
#   "intent": "other",
#   "plan": [],
#   "message": "Hi there! 👋 How can I help with your shopping today?",
#   "notes": "greeting"
# }}

# Always return valid JSON only.
# """
#         self.timeout = timeout


#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 400
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]

#     async def call_groq(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {
#             "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
#             "input": prompt,
#             "temperature": 0.0
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         # feed last 5 history turns for context
#         history = ctx.get("history", []) or []
#         recent_history = history[-5:]
#         # small grounding: pass a tiny set of retrieved products (mini-RAG)
#         retrieved = rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
#         prompt = (
#             f"SessionMemory: {json.dumps(session_memory)}\n"
#             f"ConversationHistory: {json.dumps(recent_history)}\n"
#             f"RetrievedProducts: {json.dumps(retrieved)}\n\n"
#             f"User: {user_text}\n\n"
#             "Respond strictly in JSON as specified in system prompt."
#         )

#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             raise RuntimeError("No LLM provider configured (OPENAI_API_KEY or GROQ_API_KEY required)")

#         parsed = None
#         try:
#             parsed = json.loads(out)
#         except Exception:
#             import re
#             m = re.search(r"(\{.*\})", out, re.S)
#             if m:
#                 try:
#                     parsed = json.loads(m.group(1))
#                 except Exception:
#                     parsed = {"intent": "other", "plan": [], "message": None, "notes": "failed_json_parse", "raw": out}
#             else:
#                 parsed = {"intent": "other", "plan": [], "message": None, "notes": "no_json_found", "raw": out}

#         intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
#         plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
#         message = parsed.get("message") if isinstance(parsed, dict) else None
#         notes = parsed.get("notes") if isinstance(parsed, dict) else None
#         meta = parsed.get("meta") if isinstance(parsed, dict) else None

#         normalized = {
#             "intent": intent,
#             "plan": plan,
#             "message": message,
#             "notes": notes,
#             "meta": meta,
#             "raw": out
#         }

#         return NodeResult(normalized)


# class RecAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None
#         if meta:
#             recs = rec_agent.recommend_from_meta(meta, top_k=3)
#         else:
#             user_text = ctx.get("incoming_text", "")
#             recs = rec_agent.simple_keyword_recommend(user_text, top_k=3)
#         return NodeResult({"recs": recs})



# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         invs = []

#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock_local(pid, self.store_id) or {}
#             stock = inv.get("stock", 0)
#             reserved = inv.get("reserved", 0)
#             available_qty = max(stock - reserved, 0)
#             invs.append({
#                 "product_id": pid,
#                 "stock": stock,
#                 "reserved": reserved,
#                 "available_qty": available_qty,
#                 "is_available": available_qty > 0
#             })

#         return NodeResult({"inventory": invs})


# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else {}
#         sku = meta.get("sku") if isinstance(meta, dict) else None

#         if sku:
#             product_id = sku
#             prod = rec_agent.get_product_by_sku(product_id)
#             price = float(prod.get("price", 0)) if prod else 0.0
#             product_name = prod.get("name") if prod else product_id
#         else:
#             if not recs:
#                 return NodeResult({
#                     "success": False,
#                     "error": "no_recommendation_to_buy",
#                     "message": "No product selected to purchase."
#                 })
#             chosen = recs[0]
#             product_id = chosen.get("product_id")
#             price = float(chosen.get("price", 0))
#             product_name = chosen.get("name", product_id)

#         try:
#             result = await payment_agent.process_checkout_db(
#                 ctx.get("user_id", "anonymous"), product_id, price,
#                 store_id="S1", qty=1
#             )

#             # handle structured results
#             if result.get("status") == "error" and result.get("error") == "out_of_stock":
#                 return NodeResult({
#                     "success": False,
#                     "error": "out_of_stock",
#                     "message": f"Sorry, {product_name} (SKU {product_id}) is out of stock right now.",
#                     "meta": {"sku": product_id, "qty": 1, "store_id": "S1"}
#                 })

#             elif result.get("status") == "success":
#                 return NodeResult({
#                     "success": True,
#                     "message": f"Your order for {product_name} (SKU {product_id}) has been placed successfully.",
#                     "meta": result
#                 })

#             # fallback for unexpected errors
#             return NodeResult({
#                 "success": False,
#                 "error": result.get("error", "checkout_failed"),
#                 "message": "Could not complete checkout.",
#                 "meta": result
#             })

#         except Exception as e:
#             return NodeResult({
#                 "success": False,
#                 "error": "checkout_failed",
#                 "message": "An error occurred during checkout.",
#                 "details": str(e)
#             })


# class OrderAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         # fetch orders for logged-in user
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


# # ---------------- Master Runner ----------------

# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
#     session = await load_session(session_id)
#     ctx = {
#         "session_id": session_id,
#         "user_id": (user_meta or {}).get("user_id"),
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")

#     # nodes
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")
#     order_node = OrderAgentNode("order_agent")

#     for n in [llm_node, rec_node, inv_node, pay_node, order_node]:
#         g.add_node(n)

#     # run intent node first
#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []

#     # If plan empty but intent implies action, insert safe defaults
#     if not plan and intent in ("recommend", "buy"):
#         if intent == "recommend":
#             plan = ["rec_agent", "inventory_agent"]
#         elif intent == "buy":
#             plan = ["rec_agent", "inventory_agent", "payment_agent"]

#     # Validate and fuzzy-map plan
#     from difflib import get_close_matches
#     validated_plan = []
#     missing_nodes = []
#     for nid in plan:
#         if nid in g.nodes:
#             validated_plan.append(nid)
#             continue
#         matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
#         if matches:
#             mapped = matches[0]
#             validated_plan.append(mapped)
#         else:
#             lname = nid.lower()
#             mapped = None
#             if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
#                 mapped = "rec_agent"
#             elif any(tok in lname for tok in ("inventory","stock","availability")):
#                 mapped = "inventory_agent"
#             elif any(tok in lname for tok in ("pay","payment","checkout","order")):
#                 mapped = "payment_agent"
#             if mapped and mapped in g.nodes:
#                 validated_plan.append(mapped)
#             else:
#                 missing_nodes.append(nid)
#     if missing_nodes:
#         print(f"[MASTER] Ignored missing nodes from LLM (no mapping): {missing_nodes}")

#     # run nodes in validated plan (order matters)
#     for node_id in validated_plan:
#         res = await g.nodes[node_id].run(ctx)
#         ctx["node_outputs"][node_id] = res.output

#     # persist some memory if LLM returned profile info in meta
#     meta = intent_out.get("meta") or {}
#     if isinstance(meta, dict):
#         profile = meta.get("profile") or {}
#         # e.g., {"name":"aayush"}
#         if isinstance(profile, dict):
#             if profile.get("name"):
#                 mem = session.get("memory", {})
#                 mem["name"] = profile.get("name")
#                 session["memory"] = mem
                
#     # ---------------- ASSEMBLE FINAL ----------------
#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     # recs
#     recs = []
#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         final["results"]["recommendations"] = {"recs": recs}

#     # inventory
#     if "inventory_agent" in outs:
#         final["results"]["inventory"] = outs["inventory_agent"]

#     # order/payment
#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]

#     # orders (user order history)
#     if "order_agent" in outs:
#         final["results"]["orders"] = outs["order_agent"].get("orders", [])

#     # items list
#     items = []
#     for p in recs:
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#         })
#     if items:
#         final["results"]["items"] = items

#     # Determine final assistant message:
#     # Priority:
#     # 1) payment/order agent result (success or error)
#     # 2) LLM message (only if no terminal agent outcome)
#     # 3) derived messages based on intent
#     def _normalize_order_result(order_obj):
#         """
#         Normalize common shapes into a dict with keys:
#         {status: "success"|"error"|None, success: bool, order_id, message, error}
#         """
#         if not isinstance(order_obj, dict):
#             return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
#         # support both {"status":"success"} and {"success": True}
#         status = order_obj.get("status")
#         if status is None and "success" in order_obj:
#             status = "success" if bool(order_obj.get("success")) else "error"
#         order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
#         message = order_obj.get("message")
#         error = order_obj.get("error")
#         return {"status": status, "success": bool(order_obj.get("success") or (status == "success")), "order_id": order_id, "message": message, "error": error, "raw": order_obj}

#     order = final["results"].get("order", {})
#     order_norm = _normalize_order_result(order)

#     # If we have a payment/order outcome, surface it (takes precedence over LLM)
#     if order and (order_norm["success"] or order_norm["status"] in ("success", "error")):
#         if order_norm["success"] or order_norm["status"] == "success":
#             order_id = order_norm["order_id"] or (order.get("payment") or {}).get("payment_id")
#             payment_status = (order.get("payment") or {}).get("status", "unknown")
#             # prefer a message returned from agent, else synthesize one
#             final_msg = order.get("message") or order_norm.get("message") or f"Order confirmed — Order ID: {order_id}. Payment status: {payment_status}."
#             final["results"]["message"] = final_msg
#         else:
#             # error case (e.g., out_of_stock, reserve_exception, order_create_failed)
#             # prefer explicit message from agent, else synthesize friendly message
#             err = order_norm.get("error") or (order.get("error"))
#             agent_msg = order.get("message") or order.get("details")
#             if agent_msg:
#                 final_msg = agent_msg
#             elif err == "out_of_stock":
#                 # try to present product name if available
#                 sku = (order.get("meta") or {}).get("sku")
#                 final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
#             else:
#                 final_msg = f"Order failed: {err or 'unknown_error'}. Please try again."
#             final["results"]["message"] = final_msg

#     else:
#         # No terminal order outcome — fall back to LLM message or derived text
#         llm_message = intent_out.get("message")
#         if llm_message:
#             final["results"]["message"] = llm_message
#         else:
#             if intent == "recommend" and items:
#                 final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
#             elif intent == "other":
#                 # if user asked for personal info and we have memory, answer from memory
#                 if text := ctx.get("incoming_text", ""):
#                     mem = session.get("memory", {})
#                     if "name" in mem and "what is my name" in text.lower():
#                         final["results"]["message"] = f"Your name is {mem['name']}."
#                     else:
#                         final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
#                 else:
#                     final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
#             else:
#                 final["results"]["message"] = intent_out.get("notes") or "Here are the results."

#     # Debug log the final message returned to frontend
#     try:
#         print(f"[MASTER] final message -> {final['results'].get('message')}")
#     except Exception:
#         pass

#     # persist session history + memory
#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     final["llm_notes"] = intent_out.get("notes")
#     return final


#     # # ---------------- ASSEMBLE FINAL ----------------
#     # final = {"session_id": session_id, "intent": intent, "results": {}}
#     # outs = ctx["node_outputs"]

#     # # recs
#     # recs = []
#     # if "rec_agent" in outs:
#     #     recs = outs["rec_agent"].get("recs", []) or []
#     #     final["results"]["recommendations"] = {"recs": recs}

#     # # inventory
#     # if "inventory_agent" in outs:
#     #     final["results"]["inventory"] = outs["inventory_agent"]

#     # # order/payment
#     # if "payment_agent" in outs:
#     #     final["results"]["order"] = outs["payment_agent"]

#     # # orders (user order history)
#     # if "order_agent" in outs:
#     #     final["results"]["orders"] = outs["order_agent"].get("orders", [])

#     # # items list
#     # items = []
#     # for p in recs:
#     #     items.append({
#     #         "product_id": p.get("product_id"),
#     #         "name": p.get("name"),
#     #         "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#     #         "image": (p.get("images") or [None])[0] if p.get("images") else None,
#     #         "category": p.get("category"),
#     #         "attributes": p.get("attributes", {}),
#     #     })
#     # if items:
#     #     final["results"]["items"] = items

#     # # Friendly assistant message: prefer llm message, else derive
#     # llm_message = intent_out.get("message")
#     # if llm_message:
#     #     final["results"]["message"] = llm_message
#     # else:
#     #     # strict check for order success
#     #     order = final["results"].get("order", {})
#     #     if order and order.get("status") == "success" and order.get("order_id"):
#     #         final["results"]["message"] = f"Order confirmed — Order ID: {order.get('order_id')}. Payment status: {order.get('payment',{}).get('status','unknown')}"
#     #     elif order and order.get("status") == "error":
#     #         # surface error directly (e.g., out_of_stock)
#     #         final["results"]["message"] = f"Order failed: {order.get('error', 'unknown_error')}"
#     #     elif intent == "recommend" and items:
#     #         final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
#     #     elif intent == "other":
#     #         # if user asked for personal info and we have memory, answer from memory
#     #         if text := ctx.get("incoming_text",""):
#     #             mem = session.get("memory",{})
#     #             if "name" in mem and "what is my name" in text.lower():
#     #                 final["results"]["message"] = f"Your name is {mem['name']}."
#     #             else:
#     #                 final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
#     #         else:
#     #             final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
#     #     else:
#     #         final["results"]["message"] = intent_out.get("notes") or "Here are the results."

#     # # persist session history + memory
#     # session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     # mem = session.get("memory", {})
#     # mem.setdefault("recent_queries", [])
#     # mem["recent_queries"].append(text)
#     # mem["recent_queries"] = mem["recent_queries"][-5:]
#     # session["memory"] = mem
#     # session["last_updated"] = __import__("time").time()
#     # await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     # final["llm_notes"] = intent_out.get("notes")
#     # return final




########################testing only##########################



# """
# Agentic Orchestration Graph with Redis-backed session memory (omnichannel).
# - Canonical session IDs: user:{user_id}:{channel}
# - Cross-channel handoff: merge last N turns when switching channels
# - Durable user profile memory in Redis: user_profile:{user_id}
# """

# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# # import agents
# from . import rec_agent, inventory_agent, payment_agent

# # for order queries
# from backend.db import AsyncSessionLocal
# from backend import crud as db_crud


# # ---------------- Node + Graph base ----------------

# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output


# class Node:
#     def __init__(self, id: str):
#         self.id = id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})


# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node


# # ---------------- Redis-backed Session & Profile Memory ----------------

# SESSION_PREFIX = "session:"
# USER_ACTIVE_KEY_PREFIX = "user_active_session:"       # pointer to user's last active session
# USER_PROFILE_PREFIX = "user_profile:"                  # durable user profile store


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
#     """
#     Merge (append) 'from_sid' memory/history into 'into_sid' (last N turns).
#     No-op if sids are equal/empty.
#     """
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
#     """
#     Merge 'patch' into existing durable profile for user. 90d TTL by default.
#     """
#     if not user_id or not isinstance(patch, dict):
#         return
#     key = USER_PROFILE_PREFIX + user_id
#     cur = await load_user_profile(user_id)
#     cur.update({k: v for k, v in patch.items() if v is not None})
#     await redis.set(key, json.dumps(cur), ex=ttl_seconds)


# # ---------------- Nodes ----------------

# class LLMAgentNode(Node):
#     def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
#         super().__init__(id)
#         available_agents = ["rec_agent", "inventory_agent", "payment_agent"]
# #         self.system_prompt = f"""
# # You are the Retail Master Orchestrator. RESPOND IN JSON ONLY. No markdown, no prose.

# # AVAILABLE_AGENTS: {available_agents}

# # # Conversation policy (follow strictly)
# # - You are a consultative sales associate.
# # - Always ask at least ONE open-ended question unless the user explicitly says "checkout", "buy now", or provides all required details.
# # - Guide the user through stages: greet → qualify → recommend → validate → availability → promo → checkout → fulfillment → confirm → postpurchase.
# # - Don't jump to payment unless "ready_to_buy": true and required "slots" are filled (see below).
# # - Extract and accumulate user "slots" from natural language.

# # # Required slots (per general apparel/shirt flow)
# # - occasion (e.g., office, party, casual)
# # - size (e.g., 38/39/40 or S/M/L)
# # - fit (e.g., slim, regular)
# # - color_preference
# # - budget
# # - fulfillment (ship, click_collect, reserve_in_store) — ask after recommend/availability
# # - payment_method (upi, card, pos) — ask at checkout
# # - preferred_store (if they mention in-store or click&collect)
# # - phone_or_whatsapp_ok (for updates)

# # # JSON shape (STRICT)
# # {
# #   "intent": "recommend" | "buy" | "other" | "profile",
# #   "plan": [list of agent IDs to call, in order],
# #   "message": "concise natural reply for the user (1-2 sentences max)",
# #   "ask": ["one or two open-ended questions to advance the sale"],
# #   "slots": {
# #     "occasion": null | string,
# #     "size": null | string,
# #     "fit": null | string,
# #     "color_preference": null | string,
# #     "budget": null | number,
# #     "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
# #     "payment_method": null | "upi" | "card" | "pos",
# #     "preferred_store": null | string,
# #     "phone_or_whatsapp_ok": null | boolean
# #   },
# #   "ready_to_buy": boolean,
# #   "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "promo" | "checkout" | "fulfillment" | "confirm" | "postpurchase",
# #   "plan_notes": "short developer-only hint on why these agents are called (optional)",
# #   "meta": {
# #     "rec_query": optional,
# #     "filters": optional,
# #     "sku": optional,
# #     "qty": optional,
# #     "profile": optional object with stable prefs to persist (e.g., {{ "shirt_size":"M", "fit":"slim" }})
# #   }
# # }

# # # Planning rules
# # - If user asks for ideas/products: plan ["rec_agent","inventory_agent"]; set meta.rec_query/filters.
# # - If user indicates interest but slots missing: intent "recommend", include "ask" to collect missing slots.
# # - Only plan "payment_agent" when ready_to_buy=true AND slots.size, slots.fit, fulfillment AND either sku selected or first recommendation acknowledged.
# # - When user declines: keep helpful tone, offer alternatives, ask one soft question to stay helpful.

# # # Output rules
# # - Always include "ask" with at least one question except at "confirm" or clear "buy now".
# # - Keep "message" short and human.
# # - JSON must be valid.
# # """

        
#         self.system_prompt = system_prompt or f"""
# You are the Retail Master Orchestrator. You MUST respond in JSON only. No explanations, no markdown.

# AVAILABLE_AGENTS: {available_agents}

# Strict JSON shape:
# {{
#   "intent": "recommend" | "buy" | "other" | "profile",
#   "plan": [list of agent IDs to call, in order],
#   "message": "a concise human-friendly reply to show the user",
#   "notes": "developer-only short reasoning (optional)",
#   "meta": {{ ... optional structured details (e.g., rec_query, sku, qty, profile) ... }}
# }}

# RULES:
# - Include "plan" when the user expects data/action (recommendations, availability checks, buy).
# - For product suggestions: use plan ["rec_agent","inventory_agent"] and set meta.rec_query/filters.
# - For checkout: use plan ["rec_agent","inventory_agent","payment_agent"] and set meta {{"sku":"P001","qty":1}}.
# - Extract profile signals from natural language into meta.profile (e.g., {{"shirt_size":"M","fit":"slim","preferred_store":"S1"}}).
# - Respond strictly with valid JSON.
# """
#         self.timeout = timeout

#     async def call_openai(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
#         payload = {
#             "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
#             "messages": [
#                 {"role": "system", "content": self.system_prompt},
#                 {"role": "user", "content": prompt}
#             ],
#             "temperature": 0.0,
#             "max_tokens": 400
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body["choices"][0]["message"]["content"]

#     async def call_groq(self, prompt: str) -> str:
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {
#             "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
#             "input": prompt,
#             "temperature": 0.0
#         }
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         # feed last 5 history turns for context
#         history = ctx.get("history", []) or []
#         recent_history = history[-5:]
#         # tiny grounding: pass a tiny set of retrieved products (mini-RAG)
#         # tiny grounding: pass a tiny set of retrieved products (mini-RAG)
#         retrieved = await rec_agent.simple_keyword_recommend(user_text, top_k=3) or []

#         prompt = (
#             f"SessionMemory: {json.dumps(session_memory)}\n"
#             f"ConversationHistory: {json.dumps(recent_history)}\n"
#             f"RetrievedProducts: {json.dumps(retrieved)}\n\n"
#             f"User: {user_text}\n\n"
#             "Respond strictly in JSON as specified in system prompt."
#         )

#         if USE_GROQ and GROQ_API_KEY:
#             out = await self.call_groq(prompt)
#         elif OPENAI_API_KEY:
#             out = await self.call_openai(prompt)
#         else:
#             raise RuntimeError("No LLM provider configured (OPENAI_API_KEY or GROQ_API_KEY required)")

#         # robust JSON parse
#         parsed = None
#         try:
#             parsed = json.loads(out)
#         except Exception:
#             import re
#             m = re.search(r"(\{.*\})", out, re.S)
#             if m:
#                 try:
#                     parsed = json.loads(m.group(1))
#                 except Exception:
#                     parsed = {"intent": "other", "plan": [], "message": None, "notes": "failed_json_parse", "raw": out}
#             else:
#                 parsed = {"intent": "other", "plan": [], "message": None, "notes": "no_json_found", "raw": out}

#         intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
#         plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
#         message = parsed.get("message") if isinstance(parsed, dict) else None
#         notes = parsed.get("notes") if isinstance(parsed, dict) else None
#         meta = parsed.get("meta") if isinstance(parsed, dict) else None

#         normalized = {
#             "intent": intent,
#             "plan": plan,
#             "message": message,
#             "notes": notes,
#             "meta": meta,
#             "raw": out
#         }

#         return NodeResult(normalized)


# class RecAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {}) or {}
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None

#         if meta:
#             recs = await rec_agent.recommend_from_meta(meta, top_k=3)
#         else:
#             user_text = ctx.get("incoming_text", "")
#             recs = await rec_agent.simple_keyword_recommend(user_text, top_k=3)

#         return NodeResult({"recs": recs})



# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         invs = []

#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock_local(pid, self.store_id) or {}
#             stock = inv.get("stock", 0)
#             reserved = inv.get("reserved", 0)
#             available_qty = max(stock - reserved, 0)
#             invs.append({
#                 "product_id": pid,
#                 "stock": stock,
#                 "reserved": reserved,
#                 "available_qty": available_qty,
#                 "is_available": available_qty > 0
#             })

#         return NodeResult({"inventory": invs})


# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else {}
#         sku = meta.get("sku") if isinstance(meta, dict) else None

#         if sku:
#             product_id = sku
#             prod = rec_agent.get_product_by_sku(product_id)
#             price = float(prod.get("price", 0)) if prod else 0.0
#             product_name = prod.get("name") if prod else product_id
#         else:
#             if not recs:
#                 return NodeResult({
#                     "success": False,
#                     "error": "no_recommendation_to_buy",
#                     "message": "No product selected to purchase."
#                 })
#             chosen = recs[0]
#             product_id = chosen.get("product_id")
#             price = float(chosen.get("price", 0))
#             product_name = chosen.get("name", product_id)

#         try:
#             result = await payment_agent.process_checkout_db(
#                 ctx.get("user_id", "anonymous"), product_id, price,
#                 store_id="S1", qty=1
#             )

#             if result.get("status") == "error" and result.get("error") == "out_of_stock":
#                 return NodeResult({
#                     "success": False,
#                     "error": "out_of_stock",
#                     "message": f"Sorry, {product_name} (SKU {product_id}) is out of stock right now.",
#                     "meta": {"sku": product_id, "qty": 1, "store_id": "S1"}
#                 })

#             elif result.get("status") == "success":
#                 return NodeResult({
#                     "success": True,
#                     "message": f"Your order for {product_name} (SKU {product_id}) has been placed successfully.",
#                     "meta": result
#                 })

#             return NodeResult({
#                 "success": False,
#                 "error": result.get("error", "checkout_failed"),
#                 "message": "Could not complete checkout.",
#                 "meta": result
#             })

#         except Exception as e:
#             return NodeResult({
#                 "success": False,
#                 "error": "checkout_failed",
#                 "message": "An error occurred during checkout.",
#                 "details": str(e)
#             })


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


# # ---------------- Master Runner ----------------

# def _canonicalize_session_id(raw_sid: str, user_id: Optional[str], default_channel: str = "web") -> str:
#     """
#     Map any provided session id to canonical: user:{user_id}:{channel}
#     If user_id missing, fallback to provided sid.
#     """
#     channel = default_channel
#     if ":" in (raw_sid or ""):
#         channel = (raw_sid.split(":")[0] or default_channel).lower()
#     if user_id:
#         return f"user:{user_id}:{channel}"
#     return raw_sid


# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
#     """
#     Orchestrates:
#     - Canonicalize session_id -> user:{uid}:{channel}
#     - Rehydrate from last active session for user (merge last N)
#     - Load durable user_profile into session memory
#     - Run planned agents
#     - Persist extracted profile back to durable store
#     """
#     user_id = (user_meta or {}).get("user_id")
#     # Canonicalize session id
#     canonical_sid = _canonicalize_session_id(session_id, user_id=user_id, default_channel="web")
#     if canonical_sid != session_id:
#         try:
#             await merge_sessions(session_id, canonical_sid, keep_last=10)
#         except Exception:
#             pass
#         session_id = canonical_sid

#     # Rehydrate continuity from last active session (cross-channel)
#     try:
#         active_sid = await get_active_session_for_user(user_id) if user_id else None
#         if active_sid and active_sid != session_id:
#             await merge_sessions(active_sid, session_id, keep_last=10)
#     except Exception:
#         pass

#     # Load session & inject durable user profile
#     session = await load_session(session_id)
#     profile = await load_user_profile(user_id) if user_id else {}
#     session.setdefault("memory", {}).setdefault("profile", profile)

#     ctx = {
#         "session_id": session_id,
#         "user_id": user_id,
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")

#     # nodes
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")
#     order_node = OrderAgentNode("order_agent")

#     for n in [llm_node, rec_node, inv_node, pay_node, order_node]:
#         g.add_node(n)

#     # run intent node first
#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []

#     # If plan empty but intent implies action, insert safe defaults
#     if not plan and intent in ("recommend", "buy"):
#         if intent == "recommend":
#             plan = ["rec_agent", "inventory_agent"]
#         elif intent == "buy":
#             plan = ["rec_agent", "inventory_agent", "payment_agent"]

#     # Validate and fuzzy-map plan
#     from difflib import get_close_matches
#     validated_plan = []
#     missing_nodes = []
#     for nid in plan:
#         if nid in g.nodes:
#             validated_plan.append(nid)
#             continue
#         matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
#         if matches:
#             mapped = matches[0]
#             validated_plan.append(mapped)
#         else:
#             lname = nid.lower()
#             mapped = None
#             if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
#                 mapped = "rec_agent"
#             elif any(tok in lname for tok in ("inventory","stock","availability")):
#                 mapped = "inventory_agent"
#             elif any(tok in lname for tok in ("pay","payment","checkout","order")):
#                 mapped = "payment_agent"
#             if mapped and mapped in g.nodes:
#                 validated_plan.append(mapped)
#             else:
#                 missing_nodes.append(nid)
#     if missing_nodes:
#         print(f"[MASTER] Ignored missing nodes from LLM (no mapping): {missing_nodes}")

#     # run nodes in validated plan (order matters)
#     for node_id in validated_plan:
#         res = await g.nodes[node_id].run(ctx)
#         ctx["node_outputs"][node_id] = res.output

#     # Persist durable profile if LLM extracted any
#     meta = intent_out.get("meta") or {}
#     if isinstance(meta, dict):
#         profile_patch = meta.get("profile") or {}
#         if profile_patch:
#             # write to durable store
#             if user_id:
#                 await save_user_profile(user_id, profile_patch)
#             # also reflect into session memory immediately
#             session["memory"].setdefault("profile", {}).update(profile_patch)

#     # ---------------- ASSEMBLE FINAL ----------------
#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     # recs
#     recs = []
#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         final["results"]["recommendations"] = {"recs": recs}

#     # inventory
#     if "inventory_agent" in outs:
#         final["results"]["inventory"] = outs["inventory_agent"]

#     # order/payment
#     if "payment_agent" in outs:
#         final["results"]["order"] = outs["payment_agent"]

#     # orders (user order history)
#     if "order_agent" in outs:
#         final["results"]["orders"] = outs["order_agent"].get("orders", [])

#     # items list (flattened for frontends)
#     items = []
#     for p in recs:
#         items.append({
#             "product_id": p.get("product_id"),
#             "name": p.get("name"),
#             "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
#             "image": (p.get("images") or [None])[0] if p.get("images") else None,
#             "category": p.get("category"),
#             "attributes": p.get("attributes", {}),
#         })
#     if items:
#         final["results"]["items"] = items

#     # Determine final assistant message:
#     def _normalize_order_result(order_obj):
#         if not isinstance(order_obj, dict):
#             return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
#         status = order_obj.get("status")
#         if status is None and "success" in order_obj:
#             status = "success" if bool(order_obj.get("success")) else "error"
#         order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
#         message = order_obj.get("message")
#         error = order_obj.get("error")
#         return {"status": status, "success": bool(order_obj.get("success") or (status == "success")), "order_id": order_id, "message": message, "error": error, "raw": order_obj}

#     order = final["results"].get("order", {})
#     order_norm = _normalize_order_result(order)

#     if order and (order_norm["success"] or order_norm["status"] in ("success", "error")):
#         if order_norm["success"] or order_norm["status"] == "success":
#             order_id = order_norm["order_id"] or (order.get("payment") or {}).get("payment_id")
#             payment_status = (order.get("payment") or {}).get("status", "unknown")
#             final_msg = order.get("message") or order_norm.get("message") or f"Order confirmed — Order ID: {order_id}. Payment status: {payment_status}."
#             final["results"]["message"] = final_msg
#         else:
#             err = order_norm.get("error") or (order.get("error"))
#             agent_msg = order.get("message") or order.get("details")
#             if agent_msg:
#                 final_msg = agent_msg
#             elif err == "out_of_stock":
#                 sku = (order.get("meta") or {}).get("sku")
#                 final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
#             else:
#                 final_msg = f"Order failed: {err or 'unknown_error'}. Please try again."
#             final["results"]["message"] = final_msg
#     else:
#         llm_message = intent_out.get("message")
#         if llm_message:
#             final["results"]["message"] = llm_message
#         else:
#             if intent == "recommend" and items:
#                 final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
#             elif intent == "other":
#                 txt = ctx.get("incoming_text", "") or ""
#                 mem = session.get("memory", {})
#                 if "name" in mem and "what is my name" in txt.lower():
#                     final["results"]["message"] = f"Your name is {mem['name']}."
#                 else:
#                     final["results"]["message"] = "Hello! I can help you find and buy products."
#             else:
#                 final["results"]["message"] = "Here are the results."

#     try:
#         print(f"[MASTER] final message -> {final['results'].get('message')}")
#     except Exception:
#         pass

#     # persist session history + memory
#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

#     # mark active session pointer
#     if user_id:
#         await set_active_session_for_user(user_id, session_id)

#     final["llm_notes"] = intent_out.get("notes")
#     return final




##########################human like ###########################
# import os
# import json
# import uuid
# from typing import Any, Dict, Optional, List
# from dotenv import load_dotenv
# load_dotenv()

# from redis.asyncio import Redis
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis = Redis.from_url(REDIS_URL, decode_responses=True)

# import httpx
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# from . import rec_agent, inventory_agent, payment_agent , cart_agent

# from backend.db import AsyncSessionLocal
# from backend import crud as db_crud


# class NodeResult:
#     def __init__(self, output: Dict[str, Any]):
#         self.output = output


# class Node:
#     def __init__(self, id: str):
#         self.id = id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         return NodeResult({})


# class AgentGraph:
#     def __init__(self, graph_id: Optional[str] = None):
#         self.nodes: Dict[str, Node] = {}
#         self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

#     def add_node(self, node: Node):
#         self.nodes[node.id] = node


# SESSION_PREFIX = "session:"
# USER_ACTIVE_KEY_PREFIX = "user_active_session:"
# USER_PROFILE_PREFIX = "user_profile:"


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
#         available_agents = ["rec_agent", "inventory_agent","cart_agent", "payment_agent", "order_agent"]
#         self.system_prompt = system_prompt or f"""
# You are the Retail Master Orchestrator. RESPOND IN JSON ONLY.

# AVAILABLE_AGENTS: {available_agents}

# - You are a consultative sales associate.
# - Always ask at least ONE open-ended question unless the user explicitly says checkout/buy now or all required details are present.
# - Stages: greet → qualify → recommend → validate → availability → promo → checkout → fulfillment → confirm → postpurchase.
# - Do not plan payment unless ready_to_buy=true and required slots are filled.
# - Extract and accumulate slots from natural language.

# Required slots:
# - occasion
# - size
# - color_preference
# - budget
# - fulfillment
# - payment_method
# - preferred_store

# Strict JSON:
# {{
#   "intent": "recommend" | "buy" | "other" | "profile",
#   "plan": [string],
#   "message": string,
#   "ask": [string],
#   "slots": {{
#     "occasion": null | string,
#     "size": null | string,
#     "fit": null | string,
#     "color_preference": null | string,
#     "budget": null | number,
#     "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
#     "payment_method": null | "upi" | "card" | "pos",
#     "preferred_store": null | string,
#     "phone_or_whatsapp_ok": null | boolean
#   }},
#   "ready_to_buy": boolean,
#   "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "promo" | "checkout" | "fulfillment" | "confirm" | "postpurchase",
#   "plan_notes": string,
#   "meta": {{
#     "rec_query": optional,
#     "filters": optional,
#     "sku": optional,
#     "qty": optional,
#     "confirm_selection": optional boolean,
#     "profile": optional
#   }}
# }}

# Planning:
# - Ideas/products: plan ["rec_agent","inventory_agent"], set meta.rec_query/filters.
# - If interest but slots missing: intent "recommend", include "ask" to collect.
# - If user says "add to cart" or similar: plan ["cart_agent"] and include meta { "add": "first_rec" | "product_id" }
# - Only add "payment_agent" when ready_to_buy=true and size, fit, fulfillment present and sku selected or acknowledged.
# - If decline, stay helpful and ask one soft question.

# Output:
# - Always include "ask" with at least one question except at confirm or explicit buy now.
# - Keep "message" short.
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
#         headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
#         payload = {"model": "groq-llama3-70b-mini", "input": prompt, "temperature": 0.0}
#         async with httpx.AsyncClient(timeout=self.timeout) as client:
#             r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
#             r.raise_for_status()
#             body = r.json()
#             return body.get("output", "") or body.get("text", "")

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         user_text = ctx.get("incoming_text", "")
#         session_memory = ctx.get("memory", {})
#         history = ctx.get("history", []) or []
#         recent_history = history[-5:]
#         retrieved = await rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
#         fewshot = {
#             "intent": "recommend",
#             "plan": ["rec_agent", "inventory_agent"],
#             "message": "Here’s a shirt that matches your style.",
#             "ask": ["What occasion are you shopping for?", "Do you prefer slim or regular fit?"],
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
#         if meta:
#             recs = await rec_agent.recommend_from_meta(meta, top_k=3)
#             if not recs:
#                 recs = await rec_agent.simple_keyword_recommend(meta.get("rec_query") or "", top_k=3, filters=pref_filters or meta.get("filters"))
#         else:
#             user_text = ctx.get("incoming_text", "")
#             recs = await rec_agent.simple_keyword_recommend(user_text, top_k=3, filters=pref_filters)
#         recs = recs or []
#         for r in recs:
#             r["complements"] = rec_agent.complementary_for(r)
#         return NodeResult({"recs": recs})


# class InventoryAgentNode(Node):
#     def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
#         super().__init__(id)
#         self.store_id = store_id

#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         invs = []
#         for p in recs:
#             pid = p.get("product_id")
#             inv = inventory_agent.check_stock_local(pid, self.store_id) or {}
#             stock = inv.get("stock", 0)
#             reserved = inv.get("reserved", 0)
#             available_qty = max(stock - reserved, 0)
#             invs.append({
#                 "product_id": pid,
#                 "stock": stock,
#                 "reserved": reserved,
#                 "available_qty": available_qty,
#                 "is_available": available_qty > 0
#             })
#         return NodeResult({"inventory": invs})


# class PaymentAgentNode(Node):
#     async def run(self, ctx: Dict[str, Any]) -> NodeResult:
#         nodouts = ctx.get("node_outputs", {})
#         recs = nodouts.get("rec_agent", {}).get("recs", [])
#         llm_intent = nodouts.get("llm_intent") or {}
#         meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else {}
#         slots = llm_intent.get("slots") or {}
#         ready_to_buy = bool(llm_intent.get("ready_to_buy"))
#         sku = meta.get("sku") if isinstance(meta, dict) else None
#         confirmed = bool((meta or {}).get("confirm_selection"))
#         required_for_checkout = ["size", "fit", "fulfillment"]
#         missing_required = [k for k in required_for_checkout if not slots.get(k)]
#         if not ready_to_buy or missing_required:
#             return NodeResult({
#                 "success": False,
#                 "error": "not_ready",
#                 "message": "I can place the order once I have size, fit and fulfillment preference."
#             })
#         if not sku and not confirmed:
#             return NodeResult({
#                 "success": False,
#                 "error": "selection_not_confirmed",
#                 "message": "Should I proceed with the first recommendation, or would you like to pick a specific one?"
#             })
#         if sku:
#             product_id = sku
#             prod = await rec_agent.get_product_by_sku(product_id)
#             price = float(prod.get("price", 0)) if prod else 0.0
#             product_name = prod.get("name") if prod else product_id
#         else:
#             if not recs:
#                 return NodeResult({"success": False,"error": "no_recommendation_to_buy","message": "No product selected to purchase."})
#             chosen = recs[0]
#             product_id = chosen.get("product_id")
#             price = float(chosen.get("price", 0))
#             product_name = chosen.get("name", product_id)
#         try:
#             result = await payment_agent.process_checkout_db(
#                 ctx.get("user_id", "anonymous"), product_id, price, store_id="S1", qty=1
#             )
#             if result.get("status") == "error" and result.get("error") == "out_of_stock":
#                 return NodeResult({"success": False,"error": "out_of_stock","message": f"Sorry, {product_name} (SKU {product_id}) is out of stock right now.","meta": {"sku": product_id, "qty": 1, "store_id": "S1"}})
#             elif result.get("status") == "success":
#                 return NodeResult({"success": True,"message": f"Your order for {product_name} (SKU {product_id}) has been placed successfully.","meta": result})
#             return NodeResult({"success": False,"error": result.get("error", "checkout_failed"),"message": "Could not complete checkout.","meta": result})
#         except Exception as e:
#             return NodeResult({"success": False,"error": "checkout_failed","message": "An error occurred during checkout.","details": str(e)})


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


# def _canonicalize_session_id(raw_sid: str, user_id: Optional[str], default_channel: str = "web") -> str:
#     channel = default_channel
#     if ":" in (raw_sid or ""):
#         channel = (raw_sid.split(":")[0] or default_channel).lower()
#     if user_id:
#         return f"user:{user_id}:{channel}"
#     return raw_sid


# async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
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
#     profile = await load_user_profile(user_id) if user_id else {}
#     session.setdefault("memory", {}).setdefault("profile", profile)
#     ctx = {
#         "session_id": session_id,
#         "user_id": user_id,
#         "incoming_text": text,
#         "memory": session.get("memory", {}),
#         "history": session.get("history", []),
#         "node_outputs": {}
#     }

#     g = AgentGraph(graph_id=f"master-{session_id[:8]}")
#     llm_node = LLMAgentNode()
#     rec_node = RecAgentNode("rec_agent")
#     inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
#     pay_node = PaymentAgentNode("payment_agent")
#     order_node = OrderAgentNode("order_agent")
#     for n in [llm_node, rec_node, inv_node, pay_node, order_node]:
#         g.add_node(n)

#     intent_res = await llm_node.run(ctx)
#     ctx["node_outputs"]["llm_intent"] = intent_res.output
#     intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
#     intent = intent_out.get("intent", "other")
#     plan = intent_out.get("plan", []) or []
#     slots = (intent_out.get("slots") or {}) if isinstance(intent_out, dict) else {}
#     ready_to_buy = bool(intent_out.get("ready_to_buy"))
#     next_stage = intent_out.get("next_stage") or "qualify"

#     if not plan and intent in ("recommend", "buy"):
#         if intent == "recommend":
#             plan = ["rec_agent", "inventory_agent"]
#         elif intent == "buy":
#             plan = ["rec_agent", "inventory_agent", "payment_agent"]

#     required_for_checkout = ["size", "fit", "fulfillment"]
#     missing_required = [k for k in required_for_checkout if not slots.get(k)]
#     if "payment_agent" in plan and (missing_required or not ready_to_buy):
#         plan = [p for p in plan if p != "payment_agent"]

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
#             elif any(tok in lname for tok in ("pay","payment","checkout","order")):
#                 mapped = "payment_agent"
#             if mapped and mapped in g.nodes:
#                 validated_plan.append(mapped)
#             else:
#                 missing_nodes.append(nid)

#     for node_id in validated_plan:
#         res = await g.nodes[node_id].run(ctx)
#         ctx["node_outputs"][node_id] = res.output

#     meta = intent_out.get("meta") or {}
#     if isinstance(meta, dict):
#         profile_patch = meta.get("profile") or {}
#         if profile_patch and user_id:
#             await save_user_profile(user_id, profile_patch)
#             session["memory"].setdefault("profile", {}).update(profile_patch)
#     slot_patch = {k: v for k, v in (slots or {}).items() if v not in (None, "", [])}
#     if slot_patch and user_id:
#         await save_user_profile(user_id, slot_patch)
#         session["memory"].setdefault("profile", {}).update(slot_patch)

#     final = {"session_id": session_id, "intent": intent, "results": {}}
#     outs = ctx["node_outputs"]

#     recs = []
#     if "rec_agent" in outs:
#         recs = outs["rec_agent"].get("recs", []) or []
#         final["results"]["recommendations"] = {"recs": recs}

#     if "inventory_agent" in outs:
#         final["results"]["inventory"] = outs["inventory_agent"]

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

#     def _normalize_order_result(order_obj):
#         if not isinstance(order_obj, dict):
#             return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
#         status = order_obj.get("status")
#         if status is None and "success" in order_obj:
#             status = "success" if bool(order_obj.get("success")) else "error"
#         order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
#         message = order_obj.get("message")
#         error = order_obj.get("error")
#         return {"status": status, "success": bool(order_obj.get("success") or (status == "success")), "order_id": order_id, "message": message, "error": error, "raw": order_obj}

#     order = final["results"].get("order", {})
#     order_norm = _normalize_order_result(order)

#     def _merge_msg_and_questions(msg: Optional[str], qs: List[str]) -> str:
#         msg = (msg or "").strip()
#         if qs:
#             q = " ".join([f"{qs[0]}"] + ([qs[1]] if len(qs) > 1 else []))
#             return (msg + (" " if msg else "")) + q
#         return msg or "How can I help you find the right piece today?"

#     if order and (order_norm["success"] or order_norm["status"] in ("success", "error")):
#         if order_norm["success"] or order_norm["status"] == "success":
#             order_id = order_norm["order_id"] or (order.get("payment") or {}).get("payment_id")
#             payment_status = (order.get("payment") or {}).get("status", "unknown")
#             final_msg = order.get("message") or order_norm.get("message") or f"Order confirmed — Order ID: {order_id}. Payment status: {payment_status}."
#             final["results"]["message"] = final_msg
#         else:
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
#     else:
#         llm_message = intent_out.get("message")
#         llm_ask = intent_out.get("ask") or []
#         if llm_message or llm_ask:
#             final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
#         else:
#             if intent == "recommend" and items:
#                 final["results"]["message"] = f"I found {len(items)} items — here are the top matches. What occasion are you shopping for?"
#             elif intent == "other":
#                 txt = ctx.get("incoming_text", "") or ""
#                 mem = session.get("memory", {})
#                 if "name" in mem and "what is my name" in txt.lower():
#                     final["results"]["message"] = f"Your name is {mem['name']}."
#                 else:
#                     final["results"]["message"] = "Hello! I can help you find and buy products. What occasion are you shopping for?"
#             else:
#                 final["results"]["message"] = "Here are the results. Would you like casual or office wear?"

#     try:
#         print(f"[MASTER] final message -> {final['results'].get('message')}")
#     except Exception:
#         pass

#     session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"], "slots": slots, "next_stage": next_stage})
#     mem = session.get("memory", {})
#     mem.setdefault("recent_queries", [])
#     mem["recent_queries"].append(text)
#     mem["recent_queries"] = mem["recent_queries"][-5:]
#     session["memory"] = mem
#     session["last_updated"] = __import__("time").time()
#     await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)
#     if user_id:
#         await set_active_session_for_user(user_id, session_id)
#     final["llm_notes"] = intent_out.get("notes")
#     final["slots"] = slots
#     final["next_stage"] = next_stage
#     final["ready_to_buy"] = ready_to_buy
#     return final



#####################cart added##########################



# backend/agents/master_graph.py
########################## human like ###########################
import os
import json
import uuid
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
load_dotenv()

from redis.asyncio import Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis = Redis.from_url(REDIS_URL, decode_responses=True)

import httpx
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_GROQ = os.getenv("USE_GROQ", "false").lower() in ("1", "true", "yes")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

from . import rec_agent, inventory_agent, payment_agent, cart_agent

from backend.db import AsyncSessionLocal
from backend import crud as db_crud


class NodeResult:
    def __init__(self, output: Dict[str, Any]):
        self.output = output


class Node:
    def __init__(self, id: str):
        self.id = id

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        return NodeResult({})


class AgentGraph:
    def __init__(self, graph_id: Optional[str] = None):
        self.nodes: Dict[str, Node] = {}
        self.graph_id = graph_id or ("graph-" + uuid.uuid4().hex[:8])

    def add_node(self, node: Node):
        self.nodes[node.id] = node


SESSION_PREFIX = "session:"
USER_ACTIVE_KEY_PREFIX = "user_active_session:"
USER_PROFILE_PREFIX = "user_profile:"


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


class LLMAgentNode(Node):
    def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
        super().__init__(id)
        available_agents = ["rec_agent", "inventory_agent", "cart_agent", "payment_agent", "order_agent"]
        self.system_prompt = system_prompt or f"""
You are the Retail Master Orchestrator. RESPOND IN JSON ONLY.

AVAILABLE_AGENTS: {available_agents}

- You are a consultative sales associate.
- Always ask at least ONE open-ended question unless the user explicitly says checkout/buy now or all required details are present.
- Stages: greet → qualify → recommend → validate → availability → promo → checkout → fulfillment → confirm → postpurchase.
- Do not plan payment unless ready_to_buy=true and required slots are filled.
- Extract and accumulate slots from natural language.

Required slots:
- occasion
- size
- color_preference
- budget
- fulfillment
- payment_method
- preferred_store

Strict JSON:
{{
  "intent": "recommend" | "buy" | "other" | "profile",
  "plan": [string],
  "message": string,
  "ask": [string],
  "slots": {{
    "occasion": null | string,
    "size": null | string,
    "fit": null | string,
    "color_preference": null | string,
    "budget": null | number,
    "fulfillment": null | "ship" | "click_collect" | "reserve_in_store",
    "payment_method": null | "upi" | "card" | "pos",
    "preferred_store": null | string,
    "phone_or_whatsapp_ok": null | boolean
  }},
  "ready_to_buy": boolean,
  "next_stage": "greet" | "qualify" | "recommend" | "validate" | "availability" | "promo" | "checkout" | "fulfillment" | "confirm" | "postpurchase",
  "plan_notes": string,
  "meta": {{
    "rec_query": optional,
    "filters": optional,
    "sku": optional,
    "qty": optional,
    "confirm_selection": optional boolean,
    "add": optional,                 # "first_rec" | "product_id"
    "product_id": optional,
    "profile": optional
  }}
}}

Planning:
- Ideas/products: plan ["rec_agent","inventory_agent"], set meta.rec_query/filters.
- If interest but slots missing: intent "recommend", include "ask" to collect.
- If user says "add to cart" or similar: plan ["cart_agent"] and include meta {{ "add": "first_rec" | "product_id", "product_id": "..." }}
- Only add "payment_agent" when ready_to_buy=true and size, fit, fulfillment present and sku selected or acknowledged.
- If decline, stay helpful and ask one soft question.

Output:
- Always include "ask" with at least one question except at confirm or explicit buy now.
- Keep "message" short.
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
        recent_history = history[-5:]
        retrieved = await rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
        fewshot = {
            "intent": "recommend",
            "plan": ["rec_agent", "inventory_agent"],
            "message": "Here’s a shirt that matches your style.",
            "ask": ["What occasion are you shopping for?", "Do you prefer slim or regular fit?"],
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
        if USE_GROQ and GROQ_API_KEY:
            out = await self.call_groq(prompt)
        elif OPENAI_API_KEY:
            out = await self.call_openai(prompt)
        else:
            raise RuntimeError("No LLM provider configured")
        try:
            parsed = json.loads(out)
        except Exception:
            import re
            m = re.search(r"(\{.*\})", out, re.S)
            parsed = json.loads(m.group(1)) if m else {"intent": "other", "plan": [], "message": None, "notes": "no_json", "raw": out}
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
        if meta:
            recs = await rec_agent.recommend_from_meta(meta, top_k=3)
            if not recs:
                recs = await rec_agent.simple_keyword_recommend(meta.get("rec_query") or "", top_k=3, filters=pref_filters or meta.get("filters"))
        else:
            user_text = ctx.get("incoming_text", "")
            recs = await rec_agent.simple_keyword_recommend(user_text, top_k=3, filters=pref_filters)
        recs = recs or []
        for r in recs:
            r["complements"] = rec_agent.complementary_for(r)
        return NodeResult({"recs": recs})


class InventoryAgentNode(Node):
    def __init__(self, id: str = "inventory_agent", store_id: str = "S1"):
        super().__init__(id)
        self.store_id = store_id

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {})
        recs = nodouts.get("rec_agent", {}).get("recs", [])
        invs = []
        for p in recs:
            pid = p.get("product_id")
            inv = inventory_agent.check_stock_local(pid, self.store_id) or {}
            stock = inv.get("stock", 0)
            reserved = inv.get("reserved", 0)
            available_qty = max(stock - reserved, 0)
            invs.append({
                "product_id": pid,
                "stock": stock,
                "reserved": reserved,
                "available_qty": available_qty,
                "is_available": available_qty > 0
            })
        return NodeResult({"inventory": invs})


class CartAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        user_id = ctx.get("user_id", "anonymous")
        sid = ctx.get("session_id", "user:anon:web")
        channel = (sid.split(":")[-1] if ":" in sid else "web") or "web"

        nodouts = ctx.get("node_outputs", {})
        llm = nodouts.get("llm_intent") or {}
        meta = (llm.get("meta") or {}) if isinstance(llm, dict) else {}
        recs = nodouts.get("rec_agent", {}).get("recs", []) or []

        qty = int(meta.get("qty", 1) or 1)

        # Two modes: add explicit product_id, or add first recommendation
        if meta.get("add") == "product_id" and meta.get("product_id"):
            summary = await cart_agent.add_specific_to_cart(user_id, channel, meta["product_id"], qty=qty)
        else:
            if not recs:
                return NodeResult({"success": False, "message": "No item to add yet."})
            summary = await cart_agent.add_first_rec_to_cart(user_id, channel, recs[0], qty=qty)

        msg = f"Added to your cart. {summary['count']} item(s), subtotal ₹{summary['subtotal']}."
        return NodeResult({"success": True, "cart": summary, "message": msg})


class PaymentAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {})
        recs = nodouts.get("rec_agent", {}).get("recs", [])
        llm_intent = nodouts.get("llm_intent") or {}
        meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else {}
        slots = llm_intent.get("slots") or {}
        ready_to_buy = bool(llm_intent.get("ready_to_buy"))
        sku = meta.get("sku") if isinstance(meta, dict) else None
        confirmed = bool((meta or {}).get("confirm_selection"))
        required_for_checkout = ["size", "fit", "fulfillment"]
        missing_required = [k for k in required_for_checkout if not slots.get(k)]
        if not ready_to_buy or missing_required:
            return NodeResult({
                "success": False,
                "error": "not_ready",
                "message": "I can place the order once I have size, fit and fulfillment preference."
            })
        if not sku and not confirmed:
            return NodeResult({
                "success": False,
                "error": "selection_not_confirmed",
                "message": "Should I proceed with the first recommendation, or would you like to pick a specific one?"
            })
        if sku:
            product_id = sku
            prod = await rec_agent.get_product_by_sku(product_id)
            price = float(prod.get("price", 0)) if prod else 0.0
            product_name = prod.get("name") if prod else product_id
        else:
            if not recs:
                return NodeResult({"success": False,"error": "no_recommendation_to_buy","message": "No product selected to purchase."})
            chosen = recs[0]
            product_id = chosen.get("product_id")
            price = float(chosen.get("price", 0))
            product_name = chosen.get("name", product_id)
        try:
            result = await payment_agent.process_checkout_db(
                ctx.get("user_id", "anonymous"), product_id, price, store_id="S1", qty=1
            )
            if result.get("status") == "error" and result.get("error") == "out_of_stock":
                return NodeResult({"success": False,"error": "out_of_stock","message": f"Sorry, {product_name} (SKU {product_id}) is out of stock right now.","meta": {"sku": product_id, "qty": 1, "store_id": "S1"}})
            elif result.get("status") == "success":
                return NodeResult({"success": True,"message": f"Your order for {product_name} (SKU {product_id}) has been placed successfully.","meta": result})
            return NodeResult({"success": False,"error": result.get("error", "checkout_failed"),"message": "Could not complete checkout.","meta": result})
        except Exception as e:
            return NodeResult({"success": False,"error": "checkout_failed","message": "An error occurred during checkout.","details": str(e)})


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


def _canonicalize_session_id(raw_sid: str, user_id: Optional[str], default_channel: str = "web") -> str:
    channel = default_channel
    if ":" in (raw_sid or ""):
        channel = (raw_sid.split(":")[0] or default_channel).lower()
    if user_id:
        return f"user:{user_id}:{channel}"
    return raw_sid


async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
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
    profile = await load_user_profile(user_id) if user_id else {}
    session.setdefault("memory", {}).setdefault("profile", profile)
    ctx = {
        "session_id": session_id,
        "user_id": user_id,
        "incoming_text": text,
        "memory": session.get("memory", {}),
        "history": session.get("history", []),
        "node_outputs": {}
    }

    g = AgentGraph(graph_id=f"master-{session_id[:8]}")
    llm_node = LLMAgentNode()
    rec_node = RecAgentNode("rec_agent")
    inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
    cart_node = CartAgentNode("cart_agent")
    pay_node = PaymentAgentNode("payment_agent")
    order_node = OrderAgentNode("order_agent")
    for n in [llm_node, rec_node, inv_node, cart_node, pay_node, order_node]:
        g.add_node(n)

    intent_res = await llm_node.run(ctx)
    ctx["node_outputs"]["llm_intent"] = intent_res.output
    intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
    intent = intent_out.get("intent", "other")
    plan = intent_out.get("plan", []) or []
    slots = (intent_out.get("slots") or {}) if isinstance(intent_out, dict) else {}
    ready_to_buy = bool(intent_out.get("ready_to_buy"))
    next_stage = intent_out.get("next_stage") or "qualify"

    if not plan and intent in ("recommend", "buy"):
        if intent == "recommend":
            plan = ["rec_agent", "inventory_agent"]
        elif intent == "buy":
            plan = ["rec_agent", "inventory_agent", "payment_agent"]

    required_for_checkout = ["size", "fit", "fulfillment"]
    missing_required = [k for k in required_for_checkout if not slots.get(k)]
    if "payment_agent" in plan and (missing_required or not ready_to_buy):
        plan = [p for p in plan if p != "payment_agent"]

    from difflib import get_close_matches
    validated_plan = []
    missing_nodes = []
    for nid in plan:
        if nid in g.nodes:
            validated_plan.append(nid)
            continue
        matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
        if matches:
            validated_plan.append(matches[0])
        else:
            lname = nid.lower()
            mapped = None
            if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
                mapped = "rec_agent"
            elif any(tok in lname for tok in ("inventory","stock","availability")):
                mapped = "inventory_agent"
            elif any(tok in lname for tok in ("cart","basket","add to cart","add2cart","add")):
                mapped = "cart_agent"
            elif any(tok in lname for tok in ("pay","payment","checkout","order")):
                mapped = "payment_agent"
            if mapped and mapped in g.nodes:
                validated_plan.append(mapped)
            else:
                missing_nodes.append(nid)

    for node_id in validated_plan:
        res = await g.nodes[node_id].run(ctx)
        ctx["node_outputs"][node_id] = res.output

    meta = intent_out.get("meta") or {}
    if isinstance(meta, dict):
        profile_patch = meta.get("profile") or {}
        if profile_patch and user_id:
            await save_user_profile(user_id, profile_patch)
            session["memory"].setdefault("profile", {}).update(profile_patch)
    slot_patch = {k: v for k, v in (slots or {}).items() if v not in (None, "", [])}
    if slot_patch and user_id:
        await save_user_profile(user_id, slot_patch)
        session["memory"].setdefault("profile", {}).update(slot_patch)

    final = {"session_id": session_id, "intent": intent, "results": {}}
    outs = ctx["node_outputs"]

    recs = []
    if "rec_agent" in outs:
        recs = outs["rec_agent"].get("recs", []) or []
        final["results"]["recommendations"] = {"recs": recs}

    if "inventory_agent" in outs:
        final["results"]["inventory"] = outs["inventory_agent"]

    if "cart_agent" in outs:
        final["results"]["cart"] = outs["cart_agent"].get("cart")
        # If CartAgent produced a message, surface it
        ca_msg = outs["cart_agent"].get("message")
        if ca_msg:
            final["results"]["cart_message"] = ca_msg

    if "payment_agent" in outs:
        final["results"]["order"] = outs["payment_agent"]

    if "order_agent" in outs:
        final["results"]["orders"] = outs["order_agent"].get("orders", [])

    items = []
    for p in recs:
        items.append({
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
            "image": (p.get("images") or [None])[0] if p.get("images") else None,
            "category": p.get("category"),
            "attributes": p.get("attributes", {}),
            "complements": p.get("complements", [])
        })
    if items:
        final["results"]["items"] = items

    def _normalize_order_result(order_obj):
        if not isinstance(order_obj, dict):
            return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
        status = order_obj.get("status")
        if status is None and "success" in order_obj:
            status = "success" if bool(order_obj.get("success")) else "error"
        order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
        message = order_obj.get("message")
        error = order_obj.get("error")
        return {"status": status, "success": bool(order_obj.get("success") or (status == "success")), "order_id": order_id, "message": message, "error": error, "raw": order_obj}

    order = final["results"].get("order", {})
    order_norm = _normalize_order_result(order)

    def _merge_msg_and_questions(msg: Optional[str], qs: List[str]) -> str:
        msg = (msg or "").strip()
        if qs:
            q = " ".join([f"{qs[0]}"] + ([qs[1]] if len(qs) > 1 else []))
            return (msg + (" " if msg else "")) + q
        return msg or "How can I help you find the right piece today?"

    if order and (order_norm["success"] or order_norm["status"] in ("success", "error")):
        if order_norm["success"] or order_norm["status"] == "success":
            order_id = order_norm["order_id"] or (order.get("payment") or {}).get("payment_id")
            payment_status = (order.get("payment") or {}).get("status", "unknown")
            final_msg = order.get("message") or order_norm.get("message") or f"Order confirmed — Order ID: {order_id}. Payment status: {payment_status}."
            final["results"]["message"] = final_msg
        else:
            err = order_norm.get("error") or (order.get("error"))
            agent_msg = order.get("message") or order.get("details")
            if agent_msg:
                final_msg = agent_msg
            elif err == "out_of_stock":
                sku = (order.get("meta") or {}).get("sku")
                final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
            else:
                final_msg = f"Order failed: {err or 'unknown_error'}."
            final["results"]["message"] = final_msg
    else:
        llm_message = intent_out.get("message")
        llm_ask = intent_out.get("ask") or []
        if llm_message or llm_ask:
            final["results"]["message"] = _merge_msg_and_questions(llm_message, llm_ask)
        else:
            if intent == "recommend" and items:
                final["results"]["message"] = f"I found {len(items)} items — here are the top matches. What occasion are you shopping for?"
            elif intent == "other":
                txt = ctx.get("incoming_text", "") or ""
                mem = session.get("memory", {})
                if "name" in mem and "what is my name" in txt.lower():
                    final["results"]["message"] = f"Your name is {mem['name']}."
                else:
                    final["results"]["message"] = "Hello! I can help you find and buy products. What occasion are you shopping for?"
            else:
                final["results"]["message"] = "Here are the results. Would you like casual or office wear?"

    try:
        print(f"[MASTER] final message -> {final['results'].get('message')}")
    except Exception:
        pass

    session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"], "slots": slots, "next_stage": next_stage})
    mem = session.get("memory", {})
    mem.setdefault("recent_queries", [])
    mem["recent_queries"].append(text)
    mem["recent_queries"] = mem["recent_queries"][-5:]
    session["memory"] = mem
    session["last_updated"] = __import__("time").time()
    await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)
    if user_id:
        await set_active_session_for_user(user_id, session_id)
    final["llm_notes"] = intent_out.get("notes")
    final["slots"] = slots
    final["next_stage"] = next_stage
    final["ready_to_buy"] = ready_to_buy
    return final
