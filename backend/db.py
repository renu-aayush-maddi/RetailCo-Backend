# # # backend/db.py
# # import os
# # from dotenv import load_dotenv
# # load_dotenv()

# # from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# # from sqlalchemy.orm import sessionmaker, declarative_base

# # DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./onesale.db")

# # engine = create_async_engine(DATABASE_URL, echo=False, future=True)
# # AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
# # Base = declarative_base()

# # async def get_db():
# #     async with AsyncSessionLocal() as session:
# #         yield session




# # backend/db.py
# import os
# from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, ParseResult
# import ssl
# from dotenv import load_dotenv
# load_dotenv()

# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
# from sqlalchemy.orm import sessionmaker, declarative_base

# DATABASE_URL = os.environ.get("DATABASE_URL")
# if not DATABASE_URL:
#     raise RuntimeError("DATABASE_URL not set in environment")

# # If the URL contains 'sslmode' or 'channel_binding', remove them so they don't
# # get passed to asyncpg.connect() as unexpected keyword args.
# def strip_query_params(url: str, drop_keys=("sslmode", "channel_binding")) -> str:
#     p = urlparse(url)
#     qs = parse_qs(p.query, keep_blank_values=True)
#     changed = False
#     for k in list(qs.keys()):
#         if k in drop_keys:
#             qs.pop(k)
#             changed = True
#     if not changed:
#         return url
#     new_query = urlencode({k: v[0] for k, v in qs.items()})  # flatten values
#     newp = ParseResult(scheme=p.scheme, netloc=p.netloc, path=p.path,
#                        params=p.params, query=new_query, fragment=p.fragment)
#     return urlunparse(newp)

# CLEAN_DATABASE_URL = strip_query_params(DATABASE_URL)

# # Create a simple SSL context (optional, here we just enable SSL - let the system verify)
# # If you need custom cert handling, create a SSLContext and set verify mode, load certs, etc.
# ssl_context = ssl.create_default_context()
# # If you have to disable verification for local dev only, do NOT do this in production:
# # ssl_context.check_hostname = False
# # ssl_context.verify_mode = ssl.CERT_NONE

# connect_args = {"ssl": ssl_context}

# engine = create_async_engine(
#     CLEAN_DATABASE_URL,
#     echo=False,
#     future=True,
#     connect_args=connect_args
# )

# AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
# Base = declarative_base()


# connection error update

# backend/db.py
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, ParseResult
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from collections.abc import AsyncGenerator  # <- important

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in environment")

# Ensure async driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

def strip_query_params(url: str, drop_keys=("sslmode", "channel_binding")) -> str:
    p = urlparse(url)
    qs = parse_qs(p.query, keep_blank_values=True)
    for k in list(qs.keys()):
        if k in drop_keys:
            qs.pop(k)
    new_query = urlencode({k: v[0] for k, v in qs.items()})
    newp = ParseResult(
        scheme=p.scheme, netloc=p.netloc, path=p.path,
        params=p.params, query=new_query, fragment=p.fragment
    )
    return urlunparse(newp)

CLEAN_DATABASE_URL = strip_query_params(DATABASE_URL)

CONNECT_ARGS = {}
# If your prod DB requires SSL, uncomment:
# import ssl
# ssl_ctx = ssl.create_default_context()
# CONNECT_ARGS = {"ssl": ssl_ctx}

engine = create_async_engine(
    CLEAN_DATABASE_URL,
    echo=False,
    future=True,
    connect_args=CONNECT_ARGS,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

class Base(DeclarativeBase):
    pass

# FastAPI dependency (fix: annotate as async generator)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
