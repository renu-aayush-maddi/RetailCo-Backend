# # backend/agents/rec_agent.py
# import json
# from pathlib import Path
# from typing import List, Dict

# DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"

# def load_products() -> List[Dict]:
#     with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#         return json.load(f)

# PRODUCTS_CACHE = load_products()

# def simple_keyword_recommend(query: str, top_k: int = 3):
#     query = query.lower()
#     scored = []
#     for p in PRODUCTS_CACHE:
#         score = 0
#         text = " ".join([p["name"], p.get("category","")] + p.get("tags",[])).lower()
#         for tok in query.split():
#             if tok in text:
#                 score += 1
#         import re
#         m = re.search(r"([0-9]{2,6})", query)
#         if m:
#             budget = int(m.group(1))
#             if float(p["price"]) <= budget:
#                 score += 2
#         for t in p.get("tags",[]):
#             if t in query:
#                 score += 2
#         scored.append((score, p))
#     scored = sorted(scored, key=lambda x: x[0], reverse=True)
#     recs = [p for s,p in scored if s>0][:top_k]
#     if not recs:
#         recs = PRODUCTS_CACHE[:top_k]
#     return recs





# # backend/agents/rec_agent.py
# import json
# from pathlib import Path
# from typing import List, Dict, Optional, Any
# import re

# DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"

# def load_products() -> List[Dict[str, Any]]:
#     with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#         raw = json.load(f)
#     # normalize products: ensure fields exist and types are consistent
#     out = []
#     for p in raw:
#         prod = dict(p)  # shallow copy
#         prod.setdefault("product_id", prod.get("product_id") or prod.get("sku") or "")
#         prod.setdefault("name", prod.get("name") or "")
#         # ensure price as float
#         try:
#             prod["price"] = float(prod.get("price", 0) or 0)
#         except Exception:
#             prod["price"] = 0.0
#         # images: ensure list
#         if prod.get("images") is None:
#             prod["images"] = []
#         elif isinstance(prod["images"], str):
#             prod["images"] = [prod["images"]]
#         # tags: ensure list of strings
#         if prod.get("tags") is None:
#             prod["tags"] = []
#         # attributes/category defaults
#         prod.setdefault("category", prod.get("category") or "")
#         prod.setdefault("attributes", prod.get("attributes") or {})
#         out.append(prod)
#     return out

# PRODUCTS_CACHE: List[Dict[str, Any]] = load_products()

# def get_product_by_sku(product_id: str) -> Optional[Dict[str, Any]]:
#     """
#     Return product dict for given product_id (SKU). Case-sensitive match by default.
#     """
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id") == product_id:
#             return p
#     # try case-insensitive
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id", "").lower() == product_id.lower():
#             return p
#     return None

# def _match_filters(prod: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
#     """
#     Very small filter matcher. Supports checking attributes, category and simple equality.
#     filters example: {"style":"formal", "color":"white"}
#     """
#     if not filters:
#         return True
#     # check category
#     category = prod.get("category", "") or ""
#     attrs = prod.get("attributes", {}) or {}
#     for k, v in filters.items():
#         kv = str(v).lower()
#         # check in category
#         if kv in category.lower():
#             continue
#         # check in attributes values/keys
#         found = False
#         for ak, av in attrs.items():
#             if kv in str(ak).lower() or kv in str(av).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         # check tags
#         for t in prod.get("tags", []):
#             if kv in str(t).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         # no match for this filter key -> fail
#         return False
#     return True

# def simple_keyword_recommend(query: str, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
#     """
#     Basic keyword-based recommender with optional filters.
#     - query: free text
#     - filters: optional dict with keys to match against category/attributes/tags
#     Returns up to top_k product dicts (normalized).
#     """
#     if not query:
#         # return top products if no query (by original ordering)
#         return [dict(p) for p in PRODUCTS_CACHE[:top_k]]

#     q = query.lower()
#     tokens = [t for t in re.split(r"\s+", q) if t]
#     scored = []

#     for p in PRODUCTS_CACHE:
#         # skip if filters don't match
#         if not _match_filters(p, filters):
#             continue

#         score = 0
#         text = " ".join([p.get("name",""), p.get("category","")] + p.get("tags", [])).lower()

#         # token overlap
#         for tok in tokens:
#             if tok in text:
#                 score += 1

#         # tag exact match boosts
#         for t in (p.get("tags") or []):
#             if t.lower() in q:
#                 score += 2

#         # numeric budget parsing (e.g., "under 1000" or "budget 1500")
#         m = re.search(r"([0-9]{2,6})", q)
#         if m:
#             try:
#                 budget = float(m.group(1))
#                 if p.get("price", 0) <= budget:
#                     score += 2
#             except Exception:
#                 pass

#         # small boost if query words appear in attributes
#         for av in (p.get("attributes") or {}).values():
#             if any(tok in str(av).lower() for tok in tokens):
#                 score += 1

#         scored.append((score, p))

#     # sort by score desc, then price asc to prefer cheaper for tie
#     scored = sorted(scored, key=lambda x: (x[0], -float(x[1].get("price",0))), reverse=True)

#     recs = [dict(p) for s, p in scored if s > 0][:top_k]
#     if not recs:
#         recs = [dict(p) for p in PRODUCTS_CACHE[:top_k]]
#     return recs

# def recommend_from_meta(meta: Optional[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
#     """
#     Accept structured 'meta' that LLM may provide. Example meta shapes:
#       {"rec_query":"white formal shirt", "filters":{"style":"formal"}, "budget":1200}
#       {"sku":"P001"}   # if sku provided, return that product
#     """
#     if not meta:
#         return simple_keyword_recommend("", top_k=top_k)

#     # if explicit sku provided, try to return it first
#     sku = meta.get("sku") or meta.get("product_id")
#     if sku:
#         p = get_product_by_sku(sku)
#         if p:
#             return [dict(p)]

#     rec_query = meta.get("rec_query") or meta.get("query")
#     filters = meta.get("filters")
#     # budget may be passed as number
#     budget = meta.get("budget")
#     if isinstance(budget, (int, float)):
#         # include budget in filters by adding key 'budget' (simple)
#         # our simple recommender looks for numbers in the query string,
#         # to keep it simple, append budget to query text
#         if rec_query:
#             rec_query = f"{rec_query} {int(budget)}"
#         else:
#             rec_query = str(int(budget))

#     if rec_query:
#         return simple_keyword_recommend(rec_query, top_k=top_k, filters=filters)

#     # fallback to top products
#     return simple_keyword_recommend("", top_k=top_k)




# # backend/agents/rec_agent.py
# import json
# from pathlib import Path
# from typing import List, Dict, Optional, Any
# import re

# DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"

# def load_products() -> List[Dict[str, Any]]:
#     with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#         raw = json.load(f)
#     out = []
#     for p in raw:
#         prod = dict(p)
#         prod.setdefault("product_id", prod.get("product_id") or prod.get("sku") or "")
#         prod.setdefault("name", prod.get("name") or "")
#         try:
#             prod["price"] = float(prod.get("price", 0) or 0)
#         except Exception:
#             prod["price"] = 0.0
#         if prod.get("images") is None:
#             prod["images"] = []
#         elif isinstance(prod["images"], str):
#             prod["images"] = [prod["images"]]
#         if prod.get("tags") is None:
#             prod["tags"] = []
#         prod.setdefault("category", prod.get("category") or "")
#         prod.setdefault("attributes", prod.get("attributes") or {})
#         out.append(prod)
#     return out

# PRODUCTS_CACHE: List[Dict[str, Any]] = load_products()

# def get_product_by_sku(product_id: str) -> Optional[Dict[str, Any]]:
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id") == product_id:
#             return p
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id", "").lower() == product_id.lower():
#             return p
#     return None

# def _match_filters(prod: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
#     if not filters:
#         return True
#     category = prod.get("category", "") or ""
#     attrs = prod.get("attributes", {}) or {}
#     for k, v in (filters or {}).items():
#         kv = str(v).lower()
#         if kv in category.lower():
#             continue
#         found = False
#         for ak, av in attrs.items():
#             if kv in str(ak).lower() or kv in str(av).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         for t in prod.get("tags", []):
#             if kv in str(t).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         return False
#     return True

# def simple_keyword_recommend(query: str, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
#     if not query:
#         return []
#     q = query.lower()
#     tokens = [t for t in re.split(r"\s+", q) if t]
#     scored = []
#     for p in PRODUCTS_CACHE:
#         if not _match_filters(p, filters):
#             continue
#         score = 0
#         text = " ".join([p.get("name",""), p.get("category","")] + p.get("tags", [])).lower()
#         for tok in tokens:
#             if tok in text:
#                 score += 1
#         for t in (p.get("tags") or []):
#             if t.lower() in q:
#                 score += 2
#         m = re.search(r"([0-9]{2,6})", q)
#         if m:
#             try:
#                 budget = float(m.group(1))
#                 if p.get("price", 0) <= budget:
#                     score += 2
#             except Exception:
#                 pass
#         for av in (p.get("attributes") or {}).values():
#             if any(tok in str(av).lower() for tok in tokens):
#                 score += 1
#         scored.append((score, p))
#     scored = sorted(scored, key=lambda x: (x[0], -float(x[1].get("price",0))), reverse=True)
#     recs = [dict(p) for s, p in scored if s > 0][:top_k]
#     return recs

# def recommend_from_meta(meta: Optional[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
#     if not meta:
#         return []
#     sku = meta.get("sku") or meta.get("product_id")
#     if sku:
#         p = get_product_by_sku(sku)
#         if p:
#             return [dict(p)]
#         return []
#     rec_query = meta.get("rec_query") or meta.get("query")
#     filters = meta.get("filters")
#     budget = meta.get("budget")
#     if isinstance(budget, (int, float)):
#         if rec_query:
#             rec_query = f"{rec_query} {int(budget)}"
#         else:
#             rec_query = str(int(budget))
#     if rec_query:
#         return simple_keyword_recommend(rec_query, top_k=top_k, filters=filters)
#     return []


# # backend/agents/rec_agent.py
# import json
# from pathlib import Path
# from typing import List, Dict, Optional, Any
# import re

# DATA_DIR = Path(__file__).resolve().parents[1] / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"

# def load_products() -> List[Dict[str, Any]]:
#     with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#         raw = json.load(f)
#     out = []
#     for p in raw:
#         prod = dict(p)
#         prod.setdefault("product_id", prod.get("product_id") or prod.get("sku") or "")
#         prod.setdefault("name", prod.get("name") or "")
#         try:
#             prod["price"] = float(prod.get("price", 0) or 0)
#         except Exception:
#             prod["price"] = 0.0
#         if prod.get("images") is None:
#             prod["images"] = []
#         elif isinstance(prod["images"], str):
#             prod["images"] = [prod["images"]]
#         if prod.get("tags") is None:
#             prod["tags"] = []
#         prod.setdefault("category", prod.get("category") or "")
#         prod.setdefault("attributes", prod.get("attributes") or {})
#         out.append(prod)
#     return out

# PRODUCTS_CACHE: List[Dict[str, Any]] = load_products()

# def get_product_by_sku(product_id: str) -> Optional[Dict[str, Any]]:
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id") == product_id:
#             return p
#     for p in PRODUCTS_CACHE:
#         if p.get("product_id", "").lower() == product_id.lower():
#             return p
#     return None

# def _match_filters(prod: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
#     if not filters:
#         return True
#     category = prod.get("category", "") or ""
#     attrs = prod.get("attributes", {}) or {}
#     for k, v in (filters or {}).items():
#         kv = str(v).lower()
#         if kv in category.lower():
#             continue
#         found = False
#         for ak, av in attrs.items():
#             if kv in str(ak).lower() or kv in str(av).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         for t in prod.get("tags", []):
#             if kv in str(t).lower():
#                 found = True
#                 break
#         if found:
#             continue
#         return False
#     return True

# # ---- NEW: normalize any incoming query into a string -----------------
# def _normalize_query(q: Any) -> str:
#     if q is None:
#         return ""
#     if isinstance(q, str):
#         return q
#     if isinstance(q, (int, float)):
#         return str(q)
#     if isinstance(q, dict):
#         parts: List[str] = []
#         for k, v in q.items():
#             parts.append(str(k))
#             if isinstance(v, (list, tuple, set)):
#                 parts.extend(map(str, v))
#             else:
#                 parts.append(str(v))
#         return " ".join(parts)
#     if isinstance(q, (list, tuple, set)):
#         return " ".join(map(str, q))
#     # fallback
#     return str(q)

# def simple_keyword_recommend(query: Any, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
#     q_raw = _normalize_query(query)
#     if not q_raw:
#         return []
#     q = q_raw.lower()

#     tokens = [t for t in re.split(r"\s+", q) if t]
#     scored = []
#     for p in PRODUCTS_CACHE:
#         if not _match_filters(p, filters):
#             continue
#         score = 0
#         text = " ".join([p.get("name",""), p.get("category","")] + p.get("tags", [])).lower()
#         for tok in tokens:
#             if tok in text:
#                 score += 1
#         for t in (p.get("tags") or []):
#             if t.lower() in q:
#                 score += 2
#         m = re.search(r"([0-9]{2,6})", q)
#         if m:
#             try:
#                 budget = float(m.group(1))
#                 if p.get("price", 0) <= budget:
#                     score += 2
#             except Exception:
#                 pass
#         for av in (p.get("attributes") or {}).values():
#             if any(tok in str(av).lower() for tok in tokens):
#                 score += 1
#         scored.append((score, p))
#     scored = sorted(scored, key=lambda x: (x[0], -float(x[1].get("price",0))), reverse=True)
#     recs = [dict(p) for s, p in scored if s > 0][:top_k]
#     return recs

# def recommend_from_meta(meta: Optional[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
#     if not meta:
#         return []
#     sku = meta.get("sku") or meta.get("product_id")
#     if sku:
#         p = get_product_by_sku(sku)
#         if p:
#             return [dict(p)]
#         return []

#     rec_query = meta.get("rec_query") or meta.get("query")
#     filters = meta.get("filters")
#     budget = meta.get("budget")

#     if isinstance(budget, (int, float)):
#         if rec_query:
#             rec_query = f"{_normalize_query(rec_query)} {int(budget)}"
#         else:
#             rec_query = str(int(budget))

#     if rec_query is not None:
#         return simple_keyword_recommend(_normalize_query(rec_query), top_k=top_k, filters=filters)
#     return []




# backend/agents/rec_agent.py
import os
import json
import re
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin

from sqlalchemy import text
from backend.db import AsyncSessionLocal

# Optional: make relative image paths absolute
ASSET_BASE = os.getenv("ASSET_BASE_URL", "")  # e.g. https://api.example.com/ or http://localhost:8000/static/

def _abs_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if not ASSET_BASE:
        return u
    return urljoin(ASSET_BASE, u.lstrip("/"))

def _as_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        # try to parse stringified JSON
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [v]
    return list(v)

# ---------------- DB-backed product loader with tiny TTL cache ----------------

_CACHE = {"data": [], "ts": 0.0}
_CACHE_TTL_SEC = int(os.getenv("PRODUCT_CACHE_TTL", "30"))  # small TTL is fine

async def _load_products_db() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        rows = await session.execute(text("""
            SELECT product_id, name, category, price, images, attributes
            FROM products
        """))
        rows = rows.mappings().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        imgs = [_abs_url(x) for x in _as_list(r.get("images")) if x]
        try:
            price = float(r.get("price") or 0)
        except Exception:
            price = 0.0
        prod = {
            "product_id": r.get("product_id") or "",
            "name": r.get("name") or "",
            "category": r.get("category") or "",
            "price": price,
            "images": imgs,
            "tags": [],  # keep shape compatible
            "attributes": r.get("attributes") or {},
        }
        out.append(prod)
    return out

async def get_products(force: bool = False) -> List[Dict[str, Any]]:
    now = time.time()
    if force or not _CACHE["data"] or (now - _CACHE["ts"]) > _CACHE_TTL_SEC:
        _CACHE["data"] = await _load_products_db()
        _CACHE["ts"] = now
    return _CACHE["data"]

# ---------------- Utilities used by recommenders ----------------

async def get_product_by_sku(product_id: str) -> Optional[Dict[str, Any]]:
    for p in await get_products():
        if (p.get("product_id") or "") == product_id:
            return p
    # case-insensitive fallback
    for p in await get_products():
        if (p.get("product_id") or "").lower() == (product_id or "").lower():
            return p
    return None

def _match_filters(prod: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    category = prod.get("category", "") or ""
    attrs = prod.get("attributes", {}) or {}
    for k, v in (filters or {}).items():
        kv = str(v).lower()
        if kv in category.lower():
            continue
        found = False
        for ak, av in attrs.items():
            if kv in str(ak).lower() or kv in str(av).lower():
                found = True
                break
        if found:
            continue
        for t in prod.get("tags", []):
            if kv in str(t).lower():
                found = True
                break
        if found:
            continue
        return False
    return True

def _normalize_query(q: Any) -> str:
    if q is None:
        return ""
    if isinstance(q, str):
        return q
    if isinstance(q, (int, float)):
        return str(q)
    if isinstance(q, dict):
        parts: List[str] = []
        for k, v in q.items():
            parts.append(str(k))
            if isinstance(v, (list, tuple, set)):
                parts.extend(map(str, v))
            else:
                parts.append(str(v))
        return " ".join(parts)
    if isinstance(q, (list, tuple, set)):
        return " ".join(map(str, q))
    return str(q)

# ---------------- Recommenders (now async; DB-backed) ----------------

async def simple_keyword_recommend(query: Any, top_k: int = 3, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q_raw = _normalize_query(query)
    if not q_raw:
        return []
    q = q_raw.lower()

    tokens = [t for t in re.split(r"\s+", q) if t]
    products = await get_products()
    scored = []
    for p in products:
        if not _match_filters(p, filters):
            continue
        score = 0
        text = " ".join([p.get("name",""), p.get("category","")] + p.get("tags", [])).lower()
        for tok in tokens:
            if tok in text:
                score += 1
        for t in (p.get("tags") or []):
            if t and t.lower() in q:
                score += 2
        m = re.search(r"([0-9]{2,6})", q)
        if m:
            try:
                budget = float(m.group(1))
                if (p.get("price") or 0) <= budget:
                    score += 2
            except Exception:
                pass
        for av in (p.get("attributes") or {}).values():
            if any(tok in str(av).lower() for tok in tokens):
                score += 1
        scored.append((score, p))
    scored = sorted(scored, key=lambda x: (x[0], -float(x[1].get("price",0))), reverse=True)
    recs = [dict(p) for s, p in scored if s > 0][:top_k]
    return recs

async def recommend_from_meta(meta: Optional[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    if not meta:
        return []
    sku = meta.get("sku") or meta.get("product_id")
    if sku:
        p = await get_product_by_sku(sku)
        return [dict(p)] if p else []

    rec_query = meta.get("rec_query") or meta.get("query")
    filters = meta.get("filters")
    budget = meta.get("budget")

    if isinstance(budget, (int, float)):
        if rec_query:
            rec_query = f"{_normalize_query(rec_query)} {int(budget)}"
        else:
            rec_query = str(int(budget))

    if rec_query is not None:
        return await simple_keyword_recommend(_normalize_query(rec_query), top_k=top_k, filters=filters)
    return []
