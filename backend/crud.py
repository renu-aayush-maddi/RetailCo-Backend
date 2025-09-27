# # backend/crud.py
# from sqlalchemy import select, insert, update
# from sqlalchemy.ext.asyncio import AsyncSession
# from .models import Product, Inventory, Order
# from typing import List, Dict, Optional
# import uuid

# async def get_product(db: AsyncSession, product_id: str) -> Optional[Product]:
#     q = select(Product).where(Product.product_id == product_id)
#     r = await db.execute(q)
#     return r.scalar_one_or_none()

# async def list_products(db: AsyncSession, limit: int = 50) -> List[Product]:
#     q = select(Product).limit(limit)
#     r = await db.execute(q)
#     return r.scalars().all()

# async def upsert_product(db: AsyncSession, product: Dict):
#     obj = await get_product(db, product["product_id"])
#     if obj:
#         stmt = update(Product).where(Product.product_id==product["product_id"]).values(
#             name=product.get("name"),
#             category=product.get("category"),
#             price=product.get("price"),
#             images=product.get("images"),
#             attributes=product.get("attributes"),
#             tags=product.get("tags")
#         )
#         await db.execute(stmt)
#     else:
#         stmt = insert(Product).values(**product)
#         await db.execute(stmt)
#     await db.commit()

# async def upsert_inventory(db: AsyncSession, inv: Dict):
#     q = select(Inventory).where(Inventory.product_id==inv["product_id"], Inventory.store_id==inv["store_id"])
#     r = await db.execute(q)
#     existing = r.scalar_one_or_none()
#     if existing:
#         stmt = update(Inventory).where(Inventory.inventory_id==existing.inventory_id).values(
#             stock=inv.get("stock", existing.stock),
#             reserved=inv.get("reserved", existing.reserved)
#         )
#         await db.execute(stmt)
#     else:
#         stmt = insert(Inventory).values(**inv)
#         await db.execute(stmt)
#     await db.commit()

# # backend/crud.py (replace check_and_reserve with this)
# from sqlalchemy import text

# async def check_and_reserve(db: AsyncSession, product_id: str, store_id: str = "S1", qty: int = 1) -> bool:
#     """
#     Atomic check-and-reserve with debug logging.
#     """
#     print(f"[CRUD] check_and_reserve called for product_id={product_id}, store_id={store_id}, qty={qty}")
#     stmt = text("""
#         UPDATE inventory
#         SET reserved = reserved + :qty, last_updated = NOW()
#         WHERE product_id = :product_id
#           AND store_id = :store_id
#           AND (stock - reserved) >= :qty
#         RETURNING inventory_id, stock, reserved
#     """)
#     try:
#         result = await db.execute(stmt, {
#             "product_id": product_id,
#             "store_id": store_id,
#             "qty": qty
#         })
#         row = result.first()
#         if row:
#             await db.commit()
#             print(f"[CRUD] reserved succeeded: {row}")
#             return True
#         else:
#             await db.rollback()
#             print("[CRUD] reserved failed: insufficient stock or condition not met")
#             return False
#     except Exception as e:
#         await db.rollback()
#         print(f"[CRUD] check_and_reserve ERROR: {e}")
#         # re-raise to see stack trace in uvicorn logs (optional)
#         raise



# async def create_order(db: AsyncSession, user_id: str, items: Dict, total: float, fulfillment: str="ship"):
#     order_id = "ORD-" + uuid.uuid4().hex[:8]
#     stmt = insert(Order).values(order_id=order_id, user_id=user_id, items=items, total_amount=total, status="confirmed", fulfillment=fulfillment)
#     await db.execute(stmt)
#     await db.commit()
#     return order_id







# backend/crud.py
from sqlalchemy import select, insert, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Product, Inventory, Order, User, ChatHistory
from typing import List, Dict, Optional
import uuid
from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_product(db: AsyncSession, product_id: str) -> Optional[Product]:
    q = select(Product).where(Product.product_id == product_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def list_products(db: AsyncSession, limit: int = 50) -> List[Product]:
    q = select(Product).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()

async def upsert_product(db: AsyncSession, product: Dict):
    obj = await get_product(db, product["product_id"])
    if obj:
        stmt = update(Product).where(Product.product_id==product["product_id"]).values(
            name=product.get("name"),
            category=product.get("category"),
            price=product.get("price"),
            images=product.get("images"),
            attributes=product.get("attributes"),
            tags=product.get("tags")
        )
        await db.execute(stmt)
    else:
        stmt = insert(Product).values(**product)
        await db.execute(stmt)
    await db.commit()

async def upsert_inventory(db: AsyncSession, inv: Dict):
    q = select(Inventory).where(Inventory.product_id==inv["product_id"], Inventory.store_id==inv["store_id"])
    r = await db.execute(q)
    existing = r.scalar_one_or_none()
    if existing:
        stmt = update(Inventory).where(Inventory.inventory_id==existing.inventory_id).values(
            stock=inv.get("stock", existing.stock),
            reserved=inv.get("reserved", existing.reserved)
        )
        await db.execute(stmt)
    else:
        stmt = insert(Inventory).values(**inv)
        await db.execute(stmt)
    await db.commit()

# ---------- atomic check_and_reserve ----------
async def check_and_reserve(db: AsyncSession, product_id: str, store_id: str="S1", qty: int=1) -> bool:
    """
    Atomic check-and-reserve:
    Uses a single UPDATE ... WHERE (stock - reserved) >= :qty RETURNING ...
    Returns True if reserved, False otherwise.
    """
    print(f"[CRUD] check_and_reserve called for product_id={product_id} store_id={store_id} qty={qty}")
    stmt = text("""
        UPDATE inventory
        SET reserved = reserved + :qty, last_updated = NOW()
        WHERE product_id = :product_id
          AND store_id = :store_id
          AND (stock - reserved) >= :qty
        RETURNING inventory_id, stock, reserved
    """)
    try:
        result = await db.execute(stmt, {"product_id": product_id, "store_id": store_id, "qty": qty})
        row = result.first()
        if row:
            await db.commit()
            print(f"[CRUD] reserved succeeded -> {row}")
            return True
        else:
            await db.rollback()
            print("[CRUD] reserved failed -> insufficient stock or condition not met")
            return False
    except Exception as e:
        try:
            await db.rollback()
        except Exception:
            pass
        print(f"[CRUD] check_and_reserve ERROR: {e}")
        raise

# ---------- orders ----------
async def create_order(db: AsyncSession, user_id: str, items: Dict, total: float, fulfillment: str="ship"):
    order_id = "ORD-" + uuid.uuid4().hex[:8]
    stmt = insert(Order).values(order_id=order_id, user_id=user_id, items=items, total_amount=total, status="confirmed", fulfillment=fulfillment)
    await db.execute(stmt)
    await db.commit()
    print(f"[CRUD] create_order created order {order_id} for user {user_id}")
    return order_id



async def get_orders_for_user(db: AsyncSession, user_id: str, limit: int = 50):
    q = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()


# ---------- User auth helpers ----------
async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    q = select(User).where(User.email == email)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    q = select(User).where(User.user_id == user_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)



async def create_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    hashed = hash_password(password)
    user_id = str(uuid.uuid4())
    stmt = insert(User).values(user_id=user_id, name=name, email=email, password_hash=hashed)
    await db.execute(stmt)
    await db.commit()
    return await get_user_by_id(db, user_id)

# ---------- Chat history helpers ----------
async def create_chat_entry(db: AsyncSession, user_id: str, session_id: str, role: str, message: str, intent: Optional[str]=None, results: Optional[Dict]=None):
    stmt = insert(ChatHistory).values(
        user_id=user_id,
        session_id=session_id,
        role=role,
        message=message,
        intent=intent,
        results=results
    )
    await db.execute(stmt)
    await db.commit()

async def get_history_for_user(db: AsyncSession, user_id: str, limit: int = 100):
    q = select(ChatHistory).where(ChatHistory.user_id == user_id).order_by(ChatHistory.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()

async def get_history_for_session(db: AsyncSession, session_id: str, limit: int = 100):
    q = select(ChatHistory).where(ChatHistory.session_id == session_id).order_by(ChatHistory.created_at.desc()).limit(limit)
    r = await db.execute(q)
    return r.scalars().all()



async def get_user_by_telegram(db: AsyncSession, telegram_id: str):
    q = select(User).where(User.telegram_id == telegram_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def get_user_by_phone(db: AsyncSession, phone: str):
    q = select(User).where(User.phone_number == phone)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def link_telegram_to_user(db: AsyncSession, user_id: str, telegram_id: str):
    stmt = update(User).where(User.user_id == user_id).values(telegram_id=telegram_id)
    await db.execute(stmt)
    await db.commit()

async def upsert_guest_user_by_telegram(db: AsyncSession, telegram_id: str, name: str = None, phone: str = None):
    uid = f"tg-{telegram_id}"
    existing = await get_user_by_telegram(db, telegram_id)
    if existing:
        return existing

    # create dummy password hash for guest
    dummy_password = "guest"
    hashed = pwd_context.hash(dummy_password)

    stmt = insert(User).values(
        user_id=uid,
        name=name or uid,
        email=f"{uid}@telegram.local",
        phone_number=phone,
        telegram_id=telegram_id,
        password_hash=hashed   # <-- fix
    )
    await db.execute(stmt)
    await db.commit()

    q = select(User).where(User.user_id == uid)
    r = await db.execute(q)
    return r.scalar_one_or_none()