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
from sqlalchemy import select, insert, update, text,delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Product, Inventory, Order, User, ChatHistory ,UserManualProfile,Cart, CartItem
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



async def create_user(db: AsyncSession, name: str, email: str, password: str,phone_number: str) -> User:
    hashed = hash_password(password)
    user_id = str(uuid.uuid4())
    stmt = insert(User).values(user_id=user_id, name=name, email=email, password_hash=hashed,phone_number=phone_number)
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


#################User Manual Profile#####################
# async def get_manual_profile(db: AsyncSession, user_id: str) -> Optional[UserManualProfile]:
#     q = select(UserManualProfile).where(UserManualProfile.user_id == user_id)
#     r = await db.execute(q)
#     return r.scalar_one_or_none()



# async def get_manual_profile_with_user(db: AsyncSession, user_id: str) -> dict:
#     q = (
#         select(User, UserManualProfile)
#         .join(UserManualProfile, UserManualProfile.user_id == User.user_id, isouter=True)
#         .where(User.user_id == user_id)
#     )
#     r = await db.execute(q)
#     row = r.first()
#     if not row:
#         return {}

#     user, prof = row  # prof can be None
#     out = {
#         "user": {
#             "user_id": user.user_id,
#             "name": user.name,
#             "email": user.email,
#             "phone_number": user.phone_number,
#             "telegram_id": user.telegram_id,
#         },
#         "profile": None
#     }
#     if prof:
#         out["profile"] = {
#             "user_id": prof.user_id,
#             "sizes": prof.sizes,
#             "fit": prof.fit,
#             "style": prof.style,
#             "colors": prof.colors,
#             "price_min": prof.price_min,
#             "price_max": prof.price_max,
#             "preferred_store": prof.preferred_store,
#             "city": prof.city,
#             "brand_prefs": prof.brand_prefs,
#             "notify_channel": prof.notify_channel,
#             "measurements": prof.measurements,
#             "gender": prof.gender,
#             "updated_at": str(prof.updated_at),
#         }
#     return out

# async def upsert_manual_profile(db: AsyncSession, user_id: str, patch: Dict) -> Dict:
#     cur = await get_manual_profile(db, user_id)
#     data = {
#         "sizes": patch.get("sizes"),
#         "fit": patch.get("fit"),
#         "style": patch.get("style"),
#         "colors": patch.get("colors"),
#         "price_min": patch.get("price_min"),
#         "price_max": patch.get("price_max"),
#         "preferred_store": patch.get("preferred_store"),
#         "city": patch.get("city"),
#         "brand_prefs": patch.get("brand_prefs"),
#         "notify_channel": patch.get("notify_channel"),
#         "measurements": patch.get("measurements"),
#         "gender": patch.get("gender"),
#     }
#     if cur:
#         stmt = update(UserManualProfile).where(UserManualProfile.user_id==user_id).values(**data)
#         await db.execute(stmt)
#     else:
#         stmt = insert(UserManualProfile).values(user_id=user_id, **data)
#         await db.execute(stmt)
#     await db.commit()
#     obj = await get_manual_profile(db, user_id)
#     return {
#         "user_id": user_id,
#         "sizes": obj.sizes, "fit": obj.fit, "style": obj.style, "colors": obj.colors,
#         "price_min": obj.price_min, "price_max": obj.price_max,
#         "preferred_store": obj.preferred_store, "city": obj.city,
#         "brand_prefs": obj.brand_prefs, "notify_channel": obj.notify_channel, "measurements": obj.measurements,
#         "gender": obj.gender,
#         "updated_at": str(obj.updated_at)
#     }

# async def delete_manual_keys(db: AsyncSession, user_id: str, keys: List[str]) -> Dict:
#     cur = await get_manual_profile(db, user_id)
#     if not cur:
#         return {}
#     new_data = {}
#     for k in ["sizes","fit","style","colors","price_min","price_max","preferred_store","city","brand_prefs","notify_channel","measurements","gender"]:
#         if k in keys:
#             continue
#         new_data[k] = getattr(cur, k)
#     stmt = update(UserManualProfile).where(UserManualProfile.user_id==user_id).values(**new_data)
#     await db.execute(stmt)
#     await db.commit()
#     out = await get_manual_profile(db, user_id)
#     return {
#         "user_id": user_id,
#         "sizes": out.sizes, "fit": out.fit, "style": out.style, "colors": out.colors,
#         "price_min": out.price_min, "price_max": out.price_max,
#         "preferred_store": out.preferred_store, "city": out.city,
#         "brand_prefs": out.brand_prefs, "notify_channel": out.notify_channel, "measurements": out.measurements,
#         "gender": out.gender,
#         "updated_at": str(out.updated_at)
#     }

# ORM row (internal use)
async def get_manual_profile_row(db: AsyncSession, user_id: str) -> Optional[UserManualProfile]:
    q = select(UserManualProfile).where(UserManualProfile.user_id == user_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

# Joined dict (API responses)
async def get_manual_profile_with_user(db: AsyncSession, user_id: str) -> dict:
    q = (
        select(User, UserManualProfile)
        .join(UserManualProfile, UserManualProfile.user_id == User.user_id, isouter=True)
        .where(User.user_id == user_id)
    )
    r = await db.execute(q)
    row = r.first()
    if not row:
        return {}
    user, prof = row
    out = {
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "phone_number": user.phone_number,
            "telegram_id": user.telegram_id,
        },
        "profile": None
    }
    if prof:
        out["profile"] = {
            "user_id": prof.user_id,
            "sizes": prof.sizes,
            "fit": prof.fit,
            "style": prof.style,
            "colors": prof.colors,
            "price_min": prof.price_min,
            "price_max": prof.price_max,
            "preferred_store": prof.preferred_store,
            "city": prof.city,
            "brand_prefs": prof.brand_prefs,
            "notify_channel": prof.notify_channel,
            "measurements": prof.measurements,
            "gender": prof.gender,
            "updated_at": str(prof.updated_at),
        }
    return out

async def upsert_manual_profile(db: AsyncSession, user_id: str, patch: Dict) -> Dict:
    cur = await get_manual_profile_row(db, user_id)
    data = {
        "sizes": patch.get("sizes"),
        "fit": patch.get("fit"),
        "style": patch.get("style"),
        "colors": patch.get("colors"),
        "price_min": patch.get("price_min"),
        "price_max": patch.get("price_max"),
        "preferred_store": patch.get("preferred_store"),
        "city": patch.get("city"),
        "brand_prefs": patch.get("brand_prefs"),
        "notify_channel": patch.get("notify_channel"),
        "measurements": patch.get("measurements"),
        "gender": patch.get("gender"),
    }
    if cur:
        await db.execute(
            update(UserManualProfile)
            .where(UserManualProfile.user_id == user_id)
            .values(**data)
        )
    else:
        await db.execute(insert(UserManualProfile).values(user_id=user_id, **data))
    await db.commit()
    return await get_manual_profile_with_user(db, user_id)

async def delete_manual_keys(db: AsyncSession, user_id: str, keys: List[str]) -> Dict:
    cur = await get_manual_profile_row(db, user_id)
    if not cur:
        return await get_manual_profile_with_user(db, user_id)

    # When "deleting", set to None (or {} / [] if you prefer).
    fields = ["sizes","fit","style","colors","price_min","price_max",
              "preferred_store","city","brand_prefs","notify_channel",
              "measurements","gender"]
    new_data = {}
    for k in fields:
        if k in keys:
            new_data[k] = None
        else:
            new_data[k] = getattr(cur, k)

    await db.execute(
        update(UserManualProfile)
        .where(UserManualProfile.user_id == user_id)
        .values(**new_data)
    )
    await db.commit()
    return await get_manual_profile_with_user(db, user_id)




######################cart####################

async def get_or_create_cart(db: AsyncSession, user_id: str, channel: str) -> Cart:
    q = select(Cart).where(Cart.user_id == user_id, Cart.channel == channel)
    r = await db.execute(q)
    cart = r.scalar_one_or_none()
    if cart:
        return cart
    cart_id = "CART-" + uuid.uuid4().hex[:8]
    await db.execute(insert(Cart).values(cart_id=cart_id, user_id=user_id, channel=channel))
    await db.commit()
    q2 = select(Cart).where(Cart.cart_id == cart_id)
    r2 = await db.execute(q2)
    return r2.scalar_one_or_none()

async def add_item_to_cart(db: AsyncSession, cart_id: str, product_id: str, price: float, qty: int = 1, meta: dict = None):
    cart_item_id = "CI-" + uuid.uuid4().hex[:8]
    await db.execute(insert(CartItem).values(
        cart_item_id=cart_item_id, cart_id=cart_id, product_id=product_id,
        qty=qty, price_at_add=price, meta=meta or {}
    ))
    await db.commit()
    return cart_item_id

async def get_cart_items(db: AsyncSession, cart_id: str):
    q = select(CartItem).where(CartItem.cart_id == cart_id)
    r = await db.execute(q)
    return r.scalars().all()

async def remove_cart_item(db: AsyncSession, cart_item_id: str):
    await db.execute(delete(CartItem).where(CartItem.cart_item_id == cart_item_id))
    await db.commit()

async def clear_cart(db: AsyncSession, cart_id: str):
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart_id))
    await db.commit()
