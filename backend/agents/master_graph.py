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





# backend/agents/master_graph.py
"""
Agentic Orchestration Graph with Redis-backed session memory.
LLM decides intent + plan, then only the requested agents run.
"""

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

# import agents
from . import rec_agent, inventory_agent, payment_agent

# for order queries
from backend.db import AsyncSessionLocal
from backend import crud as db_crud


# ---------------- Node + Graph base ----------------

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


# ---------------- Session Memory ----------------

SESSION_PREFIX = "session:"


async def load_session(session_id: str) -> Dict[str, Any]:
    key = SESSION_PREFIX + session_id
    raw = await redis.get(key)
    if not raw:
        return {"session_id": session_id, "memory": {}, "history": []}
    try:
        return json.loads(raw)
    except Exception:
        return {"session_id": session_id, "memory": {}, "history": []}


async def save_session(session_id: str, session_obj: Dict[str, Any], ttl_seconds: int = 60 * 60 * 24):
    key = SESSION_PREFIX + session_id
    await redis.set(key, json.dumps(session_obj), ex=ttl_seconds)


# ---------------- Nodes ----------------

class LLMAgentNode(Node):
    def __init__(self, id: str = "llm_intent", system_prompt: Optional[str] = None, timeout: int = 15):
        super().__init__(id)
        available_agents = ["rec_agent", "inventory_agent", "payment_agent", "order_agent"]
        self.system_prompt = system_prompt or f"""
You are the Retail Master Orchestrator. You MUST respond in JSON only. No explanations, no markdown.

AVAILABLE_AGENTS: {available_agents}

Strict JSON shape:
{{
  "intent": "recommend" | "buy" | "other" | "profile",
  "plan": [list of agent IDs to call, in order],        // MUST use only IDs from AVAILABLE_AGENTS
  "message": "a concise human-friendly reply to show the user",
  "notes": "developer-only short reasoning (optional)",
  "meta": {{ ... optional structured details (e.g. rec_query, sku, qty, profile) ... }}
}}

IMPORTANT RULES:
- Always include "plan" when the user expects data/action (recommendations, availability checks, buy).
- If the user asks for product suggestions, 'plan' should include ["rec_agent","inventory_agent"] and meta.rec_query may contain the exact search string or filters.
- If the user asks to buy/place an order, 'plan' should include ["rec_agent","inventory_agent","payment_agent"] and meta should contain {{"sku":"P001","qty":1}} or similar.
- Use only agent IDs from AVAILABLE_AGENTS; if you need functionality not listed, return intent:"other" and a clarifying message.

EXAMPLES:
1) User: "show me white shirts for formal occasions"
{{
  "intent": "recommend",
  "plan": ["rec_agent","inventory_agent"],
  "message": "Great — here are a few white formal shirts I found (I included SKUs). Which would you like to try?",
  "notes": "recommendation with rec_query",
  "meta": {{"rec_query":"white formal shirt", "filters":{{"style":"formal"}}}}
}}

2) User: "I want to buy the first one (SKU P001)"
{{
  "intent": "buy",
  "plan": ["rec_agent","inventory_agent","payment_agent"],
  "message": "I can place the order for SKU P001 — shall I proceed to payment?",
  "notes": "user asked to checkout specific SKU",
  "meta": {{"sku":"P001","qty":1}}
}}

3) User: "hi"
{{
  "intent": "other",
  "plan": [],
  "message": "Hi there! 👋 How can I help with your shopping today?",
  "notes": "greeting"
}}

Always return valid JSON only.
"""
        self.timeout = timeout


    async def call_openai(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"} if OPENAI_API_KEY else {}
        payload = {
            "model": "gpt-4o-mini" if OPENAI_API_KEY else "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 400
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            body = r.json()
            return body["choices"][0]["message"]["content"]

    async def call_groq(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY else {}
        payload = {
            "model": "groq-llama3-70b-mini" if GROQ_API_KEY else "groq-demo",
            "input": prompt,
            "temperature": 0.0
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post("https://api.groq.ai/v1/complete", headers=headers, json=payload)
            r.raise_for_status()
            body = r.json()
            return body.get("output", "") or body.get("text", "")

    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        user_text = ctx.get("incoming_text", "")
        session_memory = ctx.get("memory", {})
        # feed last 5 history turns for context
        history = ctx.get("history", []) or []
        recent_history = history[-5:]
        # small grounding: pass a tiny set of retrieved products (mini-RAG)
        retrieved = rec_agent.simple_keyword_recommend(user_text, top_k=3) or []
        prompt = (
            f"SessionMemory: {json.dumps(session_memory)}\n"
            f"ConversationHistory: {json.dumps(recent_history)}\n"
            f"RetrievedProducts: {json.dumps(retrieved)}\n\n"
            f"User: {user_text}\n\n"
            "Respond strictly in JSON as specified in system prompt."
        )

        if USE_GROQ and GROQ_API_KEY:
            out = await self.call_groq(prompt)
        elif OPENAI_API_KEY:
            out = await self.call_openai(prompt)
        else:
            raise RuntimeError("No LLM provider configured (OPENAI_API_KEY or GROQ_API_KEY required)")

        parsed = None
        try:
            parsed = json.loads(out)
        except Exception:
            import re
            m = re.search(r"(\{.*\})", out, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                except Exception:
                    parsed = {"intent": "other", "plan": [], "message": None, "notes": "failed_json_parse", "raw": out}
            else:
                parsed = {"intent": "other", "plan": [], "message": None, "notes": "no_json_found", "raw": out}

        intent = parsed.get("intent", "other") if isinstance(parsed, dict) else "other"
        plan = parsed.get("plan", []) if isinstance(parsed, dict) else []
        message = parsed.get("message") if isinstance(parsed, dict) else None
        notes = parsed.get("notes") if isinstance(parsed, dict) else None
        meta = parsed.get("meta") if isinstance(parsed, dict) else None

        normalized = {
            "intent": intent,
            "plan": plan,
            "message": message,
            "notes": notes,
            "meta": meta,
            "raw": out
        }

        return NodeResult(normalized)


class RecAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {}) or {}
        llm_intent = nodouts.get("llm_intent") or {}
        meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else None
        if meta:
            recs = rec_agent.recommend_from_meta(meta, top_k=3)
        else:
            user_text = ctx.get("incoming_text", "")
            recs = rec_agent.simple_keyword_recommend(user_text, top_k=3)
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


class PaymentAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        nodouts = ctx.get("node_outputs", {})
        recs = nodouts.get("rec_agent", {}).get("recs", [])
        llm_intent = nodouts.get("llm_intent") or {}
        meta = llm_intent.get("meta") if isinstance(llm_intent, dict) else {}
        sku = meta.get("sku") if isinstance(meta, dict) else None

        if sku:
            product_id = sku
            prod = rec_agent.get_product_by_sku(product_id)
            price = float(prod.get("price", 0)) if prod else 0.0
            product_name = prod.get("name") if prod else product_id
        else:
            if not recs:
                return NodeResult({
                    "success": False,
                    "error": "no_recommendation_to_buy",
                    "message": "No product selected to purchase."
                })
            chosen = recs[0]
            product_id = chosen.get("product_id")
            price = float(chosen.get("price", 0))
            product_name = chosen.get("name", product_id)

        try:
            result = await payment_agent.process_checkout_db(
                ctx.get("user_id", "anonymous"), product_id, price,
                store_id="S1", qty=1
            )

            # handle structured results
            if result.get("status") == "error" and result.get("error") == "out_of_stock":
                return NodeResult({
                    "success": False,
                    "error": "out_of_stock",
                    "message": f"Sorry, {product_name} (SKU {product_id}) is out of stock right now.",
                    "meta": {"sku": product_id, "qty": 1, "store_id": "S1"}
                })

            elif result.get("status") == "success":
                return NodeResult({
                    "success": True,
                    "message": f"Your order for {product_name} (SKU {product_id}) has been placed successfully.",
                    "meta": result
                })

            # fallback for unexpected errors
            return NodeResult({
                "success": False,
                "error": result.get("error", "checkout_failed"),
                "message": "Could not complete checkout.",
                "meta": result
            })

        except Exception as e:
            return NodeResult({
                "success": False,
                "error": "checkout_failed",
                "message": "An error occurred during checkout.",
                "details": str(e)
            })


class OrderAgentNode(Node):
    async def run(self, ctx: Dict[str, Any]) -> NodeResult:
        # fetch orders for logged-in user
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


# ---------------- Master Runner ----------------

async def run_master(session_id: str, text: str, user_meta: Optional[Dict[str, Any]] = None):
    session = await load_session(session_id)
    ctx = {
        "session_id": session_id,
        "user_id": (user_meta or {}).get("user_id"),
        "incoming_text": text,
        "memory": session.get("memory", {}),
        "history": session.get("history", []),
        "node_outputs": {}
    }

    g = AgentGraph(graph_id=f"master-{session_id[:8]}")

    # nodes
    llm_node = LLMAgentNode()
    rec_node = RecAgentNode("rec_agent")
    inv_node = InventoryAgentNode("inventory_agent", store_id="S1")
    pay_node = PaymentAgentNode("payment_agent")
    order_node = OrderAgentNode("order_agent")

    for n in [llm_node, rec_node, inv_node, pay_node, order_node]:
        g.add_node(n)

    # run intent node first
    intent_res = await llm_node.run(ctx)
    ctx["node_outputs"]["llm_intent"] = intent_res.output
    intent_out = intent_res.output if isinstance(intent_res.output, dict) else {}
    intent = intent_out.get("intent", "other")
    plan = intent_out.get("plan", []) or []

    # If plan empty but intent implies action, insert safe defaults
    if not plan and intent in ("recommend", "buy"):
        if intent == "recommend":
            plan = ["rec_agent", "inventory_agent"]
        elif intent == "buy":
            plan = ["rec_agent", "inventory_agent", "payment_agent"]

    # Validate and fuzzy-map plan
    from difflib import get_close_matches
    validated_plan = []
    missing_nodes = []
    for nid in plan:
        if nid in g.nodes:
            validated_plan.append(nid)
            continue
        matches = get_close_matches(nid, list(g.nodes.keys()), n=1, cutoff=0.6)
        if matches:
            mapped = matches[0]
            validated_plan.append(mapped)
        else:
            lname = nid.lower()
            mapped = None
            if any(tok in lname for tok in ("recommend","rec","shirt","jean","product")):
                mapped = "rec_agent"
            elif any(tok in lname for tok in ("inventory","stock","availability")):
                mapped = "inventory_agent"
            elif any(tok in lname for tok in ("pay","payment","checkout","order")):
                mapped = "payment_agent"
            if mapped and mapped in g.nodes:
                validated_plan.append(mapped)
            else:
                missing_nodes.append(nid)
    if missing_nodes:
        print(f"[MASTER] Ignored missing nodes from LLM (no mapping): {missing_nodes}")

    # run nodes in validated plan (order matters)
    for node_id in validated_plan:
        res = await g.nodes[node_id].run(ctx)
        ctx["node_outputs"][node_id] = res.output

    # persist some memory if LLM returned profile info in meta
    meta = intent_out.get("meta") or {}
    if isinstance(meta, dict):
        profile = meta.get("profile") or {}
        # e.g., {"name":"aayush"}
        if isinstance(profile, dict):
            if profile.get("name"):
                mem = session.get("memory", {})
                mem["name"] = profile.get("name")
                session["memory"] = mem
                
    # ---------------- ASSEMBLE FINAL ----------------
    final = {"session_id": session_id, "intent": intent, "results": {}}
    outs = ctx["node_outputs"]

    # recs
    recs = []
    if "rec_agent" in outs:
        recs = outs["rec_agent"].get("recs", []) or []
        final["results"]["recommendations"] = {"recs": recs}

    # inventory
    if "inventory_agent" in outs:
        final["results"]["inventory"] = outs["inventory_agent"]

    # order/payment
    if "payment_agent" in outs:
        final["results"]["order"] = outs["payment_agent"]

    # orders (user order history)
    if "order_agent" in outs:
        final["results"]["orders"] = outs["order_agent"].get("orders", [])

    # items list
    items = []
    for p in recs:
        items.append({
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
            "image": (p.get("images") or [None])[0] if p.get("images") else None,
            "category": p.get("category"),
            "attributes": p.get("attributes", {}),
        })
    if items:
        final["results"]["items"] = items

    # Determine final assistant message:
    # Priority:
    # 1) payment/order agent result (success or error)
    # 2) LLM message (only if no terminal agent outcome)
    # 3) derived messages based on intent
    def _normalize_order_result(order_obj):
        """
        Normalize common shapes into a dict with keys:
        {status: "success"|"error"|None, success: bool, order_id, message, error}
        """
        if not isinstance(order_obj, dict):
            return {"status": None, "success": False, "order_id": None, "message": None, "error": None}
        # support both {"status":"success"} and {"success": True}
        status = order_obj.get("status")
        if status is None and "success" in order_obj:
            status = "success" if bool(order_obj.get("success")) else "error"
        order_id = order_obj.get("order_id") or (order_obj.get("meta") or {}).get("order_id")
        message = order_obj.get("message")
        error = order_obj.get("error")
        return {"status": status, "success": bool(order_obj.get("success") or (status == "success")), "order_id": order_id, "message": message, "error": error, "raw": order_obj}

    order = final["results"].get("order", {})
    order_norm = _normalize_order_result(order)

    # If we have a payment/order outcome, surface it (takes precedence over LLM)
    if order and (order_norm["success"] or order_norm["status"] in ("success", "error")):
        if order_norm["success"] or order_norm["status"] == "success":
            order_id = order_norm["order_id"] or (order.get("payment") or {}).get("payment_id")
            payment_status = (order.get("payment") or {}).get("status", "unknown")
            # prefer a message returned from agent, else synthesize one
            final_msg = order.get("message") or order_norm.get("message") or f"Order confirmed — Order ID: {order_id}. Payment status: {payment_status}."
            final["results"]["message"] = final_msg
        else:
            # error case (e.g., out_of_stock, reserve_exception, order_create_failed)
            # prefer explicit message from agent, else synthesize friendly message
            err = order_norm.get("error") or (order.get("error"))
            agent_msg = order.get("message") or order.get("details")
            if agent_msg:
                final_msg = agent_msg
            elif err == "out_of_stock":
                # try to present product name if available
                sku = (order.get("meta") or {}).get("sku")
                final_msg = f"Sorry — that item{f' (SKU {sku})' if sku else ''} is out of stock right now."
            else:
                final_msg = f"Order failed: {err or 'unknown_error'}. Please try again."
            final["results"]["message"] = final_msg

    else:
        # No terminal order outcome — fall back to LLM message or derived text
        llm_message = intent_out.get("message")
        if llm_message:
            final["results"]["message"] = llm_message
        else:
            if intent == "recommend" and items:
                final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
            elif intent == "other":
                # if user asked for personal info and we have memory, answer from memory
                if text := ctx.get("incoming_text", ""):
                    mem = session.get("memory", {})
                    if "name" in mem and "what is my name" in text.lower():
                        final["results"]["message"] = f"Your name is {mem['name']}."
                    else:
                        final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
                else:
                    final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
            else:
                final["results"]["message"] = intent_out.get("notes") or "Here are the results."

    # Debug log the final message returned to frontend
    try:
        print(f"[MASTER] final message -> {final['results'].get('message')}")
    except Exception:
        pass

    # persist session history + memory
    session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
    mem = session.get("memory", {})
    mem.setdefault("recent_queries", [])
    mem["recent_queries"].append(text)
    mem["recent_queries"] = mem["recent_queries"][-5:]
    session["memory"] = mem
    session["last_updated"] = __import__("time").time()
    await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

    final["llm_notes"] = intent_out.get("notes")
    return final


    # # ---------------- ASSEMBLE FINAL ----------------
    # final = {"session_id": session_id, "intent": intent, "results": {}}
    # outs = ctx["node_outputs"]

    # # recs
    # recs = []
    # if "rec_agent" in outs:
    #     recs = outs["rec_agent"].get("recs", []) or []
    #     final["results"]["recommendations"] = {"recs": recs}

    # # inventory
    # if "inventory_agent" in outs:
    #     final["results"]["inventory"] = outs["inventory_agent"]

    # # order/payment
    # if "payment_agent" in outs:
    #     final["results"]["order"] = outs["payment_agent"]

    # # orders (user order history)
    # if "order_agent" in outs:
    #     final["results"]["orders"] = outs["order_agent"].get("orders", [])

    # # items list
    # items = []
    # for p in recs:
    #     items.append({
    #         "product_id": p.get("product_id"),
    #         "name": p.get("name"),
    #         "price": float(p.get("price", 0)) if p.get("price") is not None else 0.0,
    #         "image": (p.get("images") or [None])[0] if p.get("images") else None,
    #         "category": p.get("category"),
    #         "attributes": p.get("attributes", {}),
    #     })
    # if items:
    #     final["results"]["items"] = items

    # # Friendly assistant message: prefer llm message, else derive
    # llm_message = intent_out.get("message")
    # if llm_message:
    #     final["results"]["message"] = llm_message
    # else:
    #     # strict check for order success
    #     order = final["results"].get("order", {})
    #     if order and order.get("status") == "success" and order.get("order_id"):
    #         final["results"]["message"] = f"Order confirmed — Order ID: {order.get('order_id')}. Payment status: {order.get('payment',{}).get('status','unknown')}"
    #     elif order and order.get("status") == "error":
    #         # surface error directly (e.g., out_of_stock)
    #         final["results"]["message"] = f"Order failed: {order.get('error', 'unknown_error')}"
    #     elif intent == "recommend" and items:
    #         final["results"]["message"] = f"I found {len(items)} items — here are the top matches."
    #     elif intent == "other":
    #         # if user asked for personal info and we have memory, answer from memory
    #         if text := ctx.get("incoming_text",""):
    #             mem = session.get("memory",{})
    #             if "name" in mem and "what is my name" in text.lower():
    #                 final["results"]["message"] = f"Your name is {mem['name']}."
    #             else:
    #                 final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
    #         else:
    #             final["results"]["message"] = intent_out.get("notes") or "Hello! I can help you find and buy products."
    #     else:
    #         final["results"]["message"] = intent_out.get("notes") or "Here are the results."

    # # persist session history + memory
    # session.setdefault("history", []).append({"incoming": text, "intent": intent, "results": final["results"]})
    # mem = session.get("memory", {})
    # mem.setdefault("recent_queries", [])
    # mem["recent_queries"].append(text)
    # mem["recent_queries"] = mem["recent_queries"][-5:]
    # session["memory"] = mem
    # session["last_updated"] = __import__("time").time()
    # await save_session(session_id, session, ttl_seconds=60 * 60 * 24 * 7)

    # final["llm_notes"] = intent_out.get("notes")
    # return final
