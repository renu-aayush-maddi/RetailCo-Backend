# # backend/app.py
# import os
# import uvicorn
# from fastapi import FastAPI
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from typing import Optional

# load_dotenv()

# from backend.agents.master_graph import run_master
# from .db import engine, Base

# app = FastAPI(title="OneSale Agentic Retail Backend - Neon Demo")

# @app.on_event("startup")
# async def startup():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

# class ChatIn(BaseModel):
#     session_id: str
#     text: str
#     channel: Optional[str] = "web"
#     user_id: Optional[str] = None

# @app.post("/chat")
# async def chat_endpoint(payload: ChatIn):
#     user_meta = {"user_id": payload.user_id}
#     result = await run_master(payload.session_id, payload.text, user_meta)
#     return result

# @app.get("/health")
# async def health():
#     return {"status":"ok"}

# if __name__ == "__main__":
#     uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT",8000)), reload=True)







# # backend/app.py
# import os
# import uvicorn
# from fastapi import FastAPI, Depends, Header, HTTPException
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from typing import Optional
# import json
# from fastapi.middleware.cors import CORSMiddleware

# load_dotenv()

# from backend.agents.master_graph import run_master
# from backend.telegram import router as telegram_router
# from backend.db import engine, Base, AsyncSessionLocal
# from backend import crud
# from backend import auth

# app = FastAPI(title="OneSale Agentic Retail Backend - Neon Demo")
# origins = [
#     "http://localhost:5173",  # Vite dev server
#     "http://127.0.0.1:5173",  # sometimes dev server binds here
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],   # allow all HTTP methods (GET, POST, OPTIONS…)
#     allow_headers=["*"],   # allow all headers (Authorization, Content-Type…)
# )
# # mount auth router
# app.include_router(auth.router)
# app.include_router(telegram_router)

# security = HTTPBearer(auto_error=False)

# @app.on_event("startup")
# async def startup():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

# class ChatIn(BaseModel):
#     session_id: str
#     text: str
#     channel: Optional[str] = "web"

# def get_user_from_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
#     if credentials is None:
#         raise HTTPException(status_code=401, detail="Missing auth token")
#     token = credentials.credentials
#     try:
#         from jose import jwt, JWTError
#         SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_long_secret")
#         ALGORITHM = "HS256"
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         if not user_id:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user_id
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# @app.post("/chat")
# async def chat_endpoint(payload: ChatIn, user_id: str = Depends(get_user_from_token)):
#     # run the agent graph with the logged-in user_id
#     user_meta = {"user_id": user_id}
#     result = await run_master(payload.session_id, payload.text, user_meta)

#     # persist chat history (user message + assistant response)
#     async with AsyncSessionLocal() as db:
#         try:
#             await crud.create_chat_entry(db, user_id, payload.session_id, "user", payload.text, intent=result.get("intent"), results=None)
#             # assistant message: store the textual message and results JSON
#             assistant_text = ""
#             # If there's a human-readable message, store it; otherwise store short JSON
#             if result.get("intent") == "other" and result["results"].get("message"):
#                 assistant_text = result["results"].get("message")
#             else:
#                 assistant_text = json.dumps(result.get("results", {}))
#             await crud.create_chat_entry(db, user_id, payload.session_id, "assistant", assistant_text, intent=result.get("intent"), results=result.get("results"))
#         except Exception as e:
#             # don't break the chat if history write fails; log instead
#             print(f"[CHAT] history save error: {e}")

#     return result

# # history endpoints
# @app.get("/history/me")
# async def my_history(user_id: str = Depends(get_user_from_token), limit: int = 100):
#     async with AsyncSessionLocal() as db:
#         rows = await crud.get_history_for_user(db, user_id, limit=limit)
#         # convert SQLAlchemy rows to dicts basic view
#         out = [{"id": r.id, "role": r.role, "message": r.message, "intent": r.intent, "results": r.results, "created_at": str(r.created_at)} for r in rows]
#         return out

# @app.get("/history")
# async def history_by_session(session_id: str, user_id: str = Depends(get_user_from_token), limit: int = 100):
#     async with AsyncSessionLocal() as db:
#         rows = await crud.get_history_for_session(db, session_id, limit=limit)
#         out = [{"id": r.id, "role": r.role, "message": r.message, "intent": r.intent, "results": r.results, "created_at": str(r.created_at)} for r in rows]
#         return out

# @app.get("/health")
# async def health():
#     return {"status":"ok"}

# if __name__ == "__main__":
#     uvicorn.run("backend.app:app", host="0.0.0.0", port=int(os.getenv("PORT",8000)), reload=True)








# connection error update

# # backend/app.py
# import os
# from contextlib import asynccontextmanager
# import uvicorn
# from fastapi import FastAPI, Depends, HTTPException
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from typing import Optional
# import json
# from fastapi.middleware.cors import CORSMiddleware

# load_dotenv()

# from backend.agents.master_graph import run_master
# from backend.telegram import router as telegram_router
# from backend.db import engine, Base, get_db
# from sqlalchemy.ext.asyncio import AsyncSession
# from backend import crud
# from jose import jwt, JWTError

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
#     yield
#     await engine.dispose()

# app = FastAPI(
#     title="OneSale Agentic Retail Backend - Neon Demo",
#     lifespan=lifespan,
# )

# origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Routers
# from backend import auth
# app.include_router(auth.router)
# app.include_router(telegram_router)

# security = HTTPBearer(auto_error=False)

# class ChatIn(BaseModel):
#     session_id: str
#     text: str
#     channel: Optional[str] = "web"

# def get_user_from_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
#     if credentials is None:
#         raise HTTPException(status_code=401, detail="Missing auth token")
#     token = credentials.credentials
#     SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_long_secret")
#     ALGORITHM = "HS256"
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         if not user_id:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user_id
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# @app.post("/chat")
# async def chat_endpoint(
#     payload: ChatIn,
#     user_id: str = Depends(get_user_from_token),
#     db: AsyncSession = Depends(get_db),
# ):
#     user_meta = {"user_id": user_id}
#     result = await run_master(payload.session_id, payload.text, user_meta)

#     try:
#         await crud.create_chat_entry(
#             db, user_id, payload.session_id, "user", payload.text,
#             intent=result.get("intent"), results=None
#         )
#         if result.get("intent") == "other" and result["results"].get("message"):
#             assistant_text = result["results"]["message"]
#         else:
#             assistant_text = json.dumps(result.get("results", {}))
#         await crud.create_chat_entry(
#             db, user_id, payload.session_id, "assistant", assistant_text,
#             intent=result.get("intent"), results=result.get("results")
#         )
#         await db.commit()
#     except Exception as e:
#         await db.rollback()
#         print(f"[CHAT] history save error: {e}")

#     return result

# @app.get("/history/me")
# async def my_history(
#     user_id: str = Depends(get_user_from_token),
#     db: AsyncSession = Depends(get_db),
#     limit: int = 100,
# ):
#     rows = await crud.get_history_for_user(db, user_id, limit=limit)
#     return [
#         {
#             "id": r.id, "role": r.role, "message": r.message,
#             "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
#         } for r in rows
#     ]

# @app.get("/history")
# async def history_by_session(
#     session_id: str,
#     user_id: str = Depends(get_user_from_token),
#     db: AsyncSession = Depends(get_db),
#     limit: int = 100,
# ):
#     rows = await crud.get_history_for_session(db, session_id, limit=limit)
#     return [
#         {
#             "id": r.id, "role": r.role, "message": r.message,
#             "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
#         } for r in rows
#     ]

# @app.get("/health")
# async def health():
#     return {"status": "ok"}

# if __name__ == "__main__":
#     uvicorn.run(
#         "backend.app:app",
#         host="0.0.0.0",
#         port=int(os.getenv("PORT", 8000)),
#         reload=True,
#     )



######################testing only##########################
# backend/app.py

import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import json
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.agents.master_graph import run_master, get_active_session_for_user
from backend.deps import get_user_from_token 
from backend.profile_manual import router as manual_router
from backend.telegram import router as telegram_router
from backend.db import engine, Base, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from backend import crud
from jose import jwt, JWTError



@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(
    title="OneSale Agentic Retail Backend - Neon Demo",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # add your deployed frontend domain(s) here
    # "https://yourapp.netlify.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from backend import auth

app.include_router(auth.router)
app.include_router(telegram_router)
app.include_router(manual_router)

security = HTTPBearer(auto_error=False)

class ChatIn(BaseModel):
    session_id: Optional[str] = None
    text: str
    channel: Optional[str] = "web"

# def get_user_from_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
#     if credentials is None:
#         raise HTTPException(status_code=401, detail="Missing auth token")
#     token = credentials.credentials
#     SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_long_secret")
#     ALGORITHM = "HS256"
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         user_id = payload.get("sub")
#         if not user_id:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return user_id
#     except JWTError:
#         raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/chat")
async def chat_endpoint(
    payload: ChatIn,
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
):
    # Canonicalize session to user:{uid}:{channel}
    channel = (payload.channel or "web").lower()
    incoming_sid = payload.session_id or f"user:{user_id}:{channel}"
    if not incoming_sid.startswith("user:"):
        incoming_sid = f"user:{user_id}:{channel}"

    user_meta = {"user_id": user_id}
    result = await run_master(incoming_sid, payload.text, user_meta)

    # persist history to DB (best effort)
    try:
        await crud.create_chat_entry(
            db, user_id, incoming_sid, "user", payload.text,
            intent=result.get("intent"), results=None
        )
        assistant_text = result["results"].get("message") or json.dumps(result.get("results", {}))
        await crud.create_chat_entry(
            db, user_id, incoming_sid, "assistant", assistant_text,
            intent=result.get("intent"), results=result.get("results")
        )
        await db.commit()
    except Exception as e:
        await db.rollback()
        print(f"[CHAT] history save error: {e}")

    return result

@app.get("/history/me")
async def my_history(
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    rows = await crud.get_history_for_user(db, user_id, limit=limit)
    return [
        {
            "id": r.id, "role": r.role, "message": r.message,
            "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
        } for r in rows
    ]

@app.get("/history")
async def history_by_session(
    session_id: str = Query(..., description="e.g., user:{uid}:web"),
    user_id: str = Depends(get_user_from_token),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
):
    rows = await crud.get_history_for_session(db, session_id, limit=limit)
    return [
        {
            "id": r.id, "role": r.role, "message": r.message,
            "intent": r.intent, "results": r.results, "created_at": str(r.created_at)
        } for r in rows
    ]

@app.get("/session/active")
async def get_active_session(channel: str = Query("web"), user_id: str = Depends(get_user_from_token)):
    """
    Returns canonical session id for the user/channel. The first /chat call will
    rehydrate from any previously active session automatically.
    """
    canonical = f"user:{user_id}:{channel}"
    # We return canonical to keep clients simple; cross-channel merge is handled in run_master
    return {"session_id": canonical}

@app.post("/session/reset")
async def reset_session(channel: str = Query("web"), user_id: str = Depends(get_user_from_token)):
    """
    Clears the current session envelope (but not the durable user profile).
    """
    from backend.agents.master_graph import save_session
    sid = f"user:{user_id}:{channel}"
    empty = {"session_id": sid, "memory": {}, "history": [], "last_updated": __import__("time").time()}
    await save_session(sid, empty, ttl_seconds=60*60*24*7)
    return {"ok": True, "session_id": sid}









############cart############################################
from pydantic import BaseModel
from typing import Optional
from backend.agents import cart_agent
from backend.agents.master_graph import load_session as load_session_from_redis

class CartAddIn(BaseModel):
    product_id: Optional[str] = None
    from_first_rec: Optional[bool] = False
    qty: Optional[int] = 1
    channel: Optional[str] = "web"
    
@app.post("/cart/add")
async def cart_add(
    payload: CartAddIn,
    user_id: str = Depends(get_user_from_token),
):
    channel = (payload.channel or "web").lower()
    if payload.from_first_rec:
        sid = f"user:{user_id}:{channel}"
        s = await load_session_from_redis(sid)
        last = (s.get("history") or [])[-1] if (s.get("history")) else None
        recs = ((last or {}).get("results") or {}).get("recommendations", {}).get("recs", []) if last else []
        if not recs:
            raise HTTPException(status_code=400, detail="No recommendations to add.")
        summary = await cart_agent.add_first_rec_to_cart(user_id, channel, recs[0], qty=payload.qty or 1)
        return {"ok": True, "cart": summary}
    else:
        if not payload.product_id:
            raise HTTPException(status_code=400, detail="product_id required")
        summary = await cart_agent.add_specific_to_cart(user_id, channel, payload.product_id, qty=payload.qty or 1)
        return {"ok": True, "cart": summary}

@app.get("/cart/summary")
async def cart_summary(
    channel: str = Query("web"),
    user_id: str = Depends(get_user_from_token),
):
    summary = await cart_agent.get_cart_summary(user_id, channel.lower())
    return {"ok": True, "cart": summary}

@app.delete("/cart/item/{cart_item_id}")
async def cart_remove_item(
    cart_item_id: str,
    channel: str = Query("web"),
    user_id: str = Depends(get_user_from_token),
):
    summary = await cart_agent.remove_item(user_id, channel.lower(), cart_item_id)
    return {"ok": True, "cart": summary}


@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )
