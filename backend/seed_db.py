# # backend/seed_db.py
# # backend/seed_db.py (top)
# import sys
# from pathlib import Path
# # ensure the package root (project root) is on sys.path so imports like `from db import ...` work
# PROJECT_ROOT = Path(__file__).resolve().parent
# sys.path.insert(0, str(PROJECT_ROOT))


# import asyncio, json
# from pathlib import Path
# from dotenv import load_dotenv
# load_dotenv()

# from db import engine, AsyncSessionLocal, Base
# from models import Product, Inventory

# DATA_DIR = Path(__file__).resolve().parent / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"
# INV_FILE = DATA_DIR / "inventory.json"

# async def seed():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     async with AsyncSessionLocal() as session:
#         with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#             products = json.load(f)
#         for p in products:
#             prod = Product(
#                 product_id=p["product_id"],
#                 name=p["name"],
#                 category=p.get("category"),
#                 price=p["price"],
#                 images=p.get("images"),
#                 attributes=p.get("attributes"),
#                 tags=p.get("tags")
#             )
#             session.add(prod)

#         with open(INV_FILE, "r", encoding="utf-8") as f:
#             invs = json.load(f)
#         for rec in invs:
#             inv = Inventory(
#                 product_id=rec["product_id"],
#                 store_id=rec["store_id"],
#                 stock=rec.get("stock",0),
#                 reserved=rec.get("reserved",0),
#                 location=rec["location"]
#             )
#             session.add(inv)

#         await session.commit()
#     print("Seeded DB with products & inventory")

# if __name__ == "__main__":
#     asyncio.run(seed())






# import sys, asyncio, json
# from pathlib import Path
# from dotenv import load_dotenv

# PROJECT_ROOT = Path(__file__).resolve().parent.parent
# sys.path.insert(0, str(PROJECT_ROOT))

# load_dotenv()

# from backend.db import engine, AsyncSessionLocal, Base
# from backend.models import Product

# DATA_DIR = Path(__file__).resolve().parent / "data"
# PRODUCTS_FILE = DATA_DIR / "products.json"

# async def seed():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

#     async with AsyncSessionLocal() as session:
#         with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
#             products = json.load(f)

#         for p in products:
#             # Await the merge operation
#             await session.merge(Product(
#                 product_id=p["product_id"],
#                 name=p["name"],
#                 category=p.get("category"),
#                 price=p["price"],
#                 images=p.get("images"),
#                 attributes=p.get("attributes"),
#                 tags=p.get("tags"),
#                 description=p.get("description")
#             ))

#         await session.commit()

#     print("Seeded DB with products")

# if __name__ == "__main__":
#     asyncio.run(seed())





# backend/seed_db.py
import sys
from pathlib import Path
# ensure the package root (project root) is on sys.path so imports like `from db import ...` work
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import asyncio, json
from dotenv import load_dotenv
load_dotenv()

from db import engine, AsyncSessionLocal, Base
from models import Inventory  # Only import Inventory model

DATA_DIR = Path(__file__).resolve().parent / "data"
INV_FILE = DATA_DIR / "inventory.json"  # Only the inventory file

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        with open(INV_FILE, "r", encoding="utf-8") as f:
            invs = json.load(f)
        for rec in invs:
            inv = Inventory(
                product_id=rec["product_id"],
                store_id=rec["store_id"],
                stock=rec.get("stock", 0),
                reserved=rec.get("reserved", 0),
                location=rec["location"]
            )
            session.add(inv)

        await session.commit()
    print("Seeded DB with inventory")

if __name__ == "__main__":
    asyncio.run(seed())
