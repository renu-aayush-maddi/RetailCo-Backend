
# backend/crud.py
from sqlalchemy import select, insert, update, text,delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from .models import Product, Inventory, Order, User, ChatHistory ,UserManualProfile,Cart, CartItem
from typing import List, Dict, Optional
import uuid
from passlib.context import CryptContext
# add near top of file
from decimal import Decimal, InvalidOperation
from math import floor



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





############LOYALITY#######################

async def get_user_loyalty(db: AsyncSession, user_id: str):
    user = await get_user_by_id(db, user_id)
    if not user:
        return {"points": 0, "tier": "Bronze", "total_spend": 0.0}
    return {
        "points": int(user.loyalty_points or 0),
        "tier": user.loyalty_tier or "Bronze",
        "total_spend": float(user.total_spend or 0.0),
    }

def _compute_tier(total_spend: Decimal) -> str:
    try:
        ts = float(total_spend)
    except Exception:
        ts = 0.0
    if ts >= 30000:
        return "Platinum"
    elif ts >= 15000:
        return "Gold"
    elif ts >= 5000:
        return "Silver"
    else:
        return "Bronze"

async def apply_loyalty_earn(db: AsyncSession, user_id: str, order_amount: float):
    """Give points after a successful paid order."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return

    # Normalize order_amount to Decimal safely
    try:
        amt = Decimal(str(order_amount))
    except (InvalidOperation, TypeError, ValueError):
        amt = Decimal(0)

    earned = floor(float(amt) / 10.0)  # 10 points per ₹100 => floor(amount/10)
    user.loyalty_points = (int(user.loyalty_points or 0) + int(earned))
    # update total_spend in Decimal form to avoid type errors
    prev = Decimal(user.total_spend or 0)
    user.total_spend = prev + amt
    user.loyalty_tier = _compute_tier(user.total_spend)

    await db.commit()

async def apply_loyalty_redeem(db: AsyncSession, user_id: str, order_amount: float):
    """
    Redeem as much as possible for this order, based on available points.
    Returns (discount_amount, points_used, remaining_points)
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return (0.0, 0, 0)

    current_points = int(user.loyalty_points or 0)
    if current_points <= 0:
        return (0.0, 0, current_points)

    # 1 point = 0.5 rupees
    try:
        max_value = Decimal(current_points) * Decimal("0.5")
    except Exception:
        max_value = Decimal(0)

    try:
        order_amt = Decimal(str(order_amount))
    except Exception:
        order_amt = Decimal(0)

    discount = min(order_amt, max_value)
    # points used = discount / 0.5
    points_used = int((discount / Decimal("0.5")).to_integral_value(rounding="ROUND_FLOOR"))
    user.loyalty_points = current_points - points_used
    await db.commit()
    return (float(discount), points_used, int(user.loyalty_points or 0))



from sqlalchemy import select
from backend.models import Inventory

async def get_inventory_for_product(session, product_id: str):
    stmt = select(
        Inventory.product_id,
        Inventory.store_id,
        Inventory.location,
        Inventory.stock,
        Inventory.reserved
    ).where(Inventory.product_id == product_id)

    res = await session.execute(stmt)
    return res.all()




from datetime import datetime, timedelta
from backend.models import Reservation


async def create_reservation(
    db: AsyncSession,
    user_id: str,
    product_id: str,
    store_id: str,
    date: str,
    time: str,
):
    print(
    "[DB] create_reservation called",
    user_id, product_id, store_id, date, time
        )

    reservation_id = "RSV-" + uuid.uuid4().hex[:8]

    stmt = insert(Reservation).values(
        reservation_id=reservation_id,
        user_id=user_id,
        product_id=product_id,
        store_id=store_id,
        date=date,
        time=time,
        status="active",
    )

    await db.execute(stmt)
    await db.commit()
    return reservation_id



# backend/crud.py

# ... existing code ...

async def confirm_stock_deduction(db: AsyncSession, product_id: str, store_id: str, qty: int):
    """
    Moves inventory from 'reserved' to permanently 'sold'.
    Decreases both 'stock' and 'reserved' by the quantity.
    """
    stmt = text("""
        UPDATE inventory
        SET stock = stock - :qty,
            reserved = reserved - :qty,
            last_updated = NOW()
        WHERE product_id = :product_id
          AND store_id = :store_id
    """)
    await db.execute(stmt, {"product_id": product_id, "store_id": store_id, "qty": qty})
    await db.commit()
    
    
    
# backend/crud.py (Add to end of file)

from .models import ReturnRequest, Feedback

# --- POST PURCHASE ---

async def get_latest_order_for_user(db: AsyncSession, user_id: str):
    """Fetch the single most recent order for context."""
    q = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(1)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def get_order_by_id(db: AsyncSession, order_id: str):
    q = select(Order).where(Order.order_id == order_id)
    r = await db.execute(q)
    return r.scalar_one_or_none()

async def create_return_request(db: AsyncSession, user_id: str, order_id: str, product_id: str, reason: str):
    return_id = "RET-" + uuid.uuid4().hex[:8]
    stmt = insert(ReturnRequest).values(
        return_id=return_id,
        user_id=user_id,
        order_id=order_id,
        product_id=product_id,
        reason=reason,
        status="approved" # Auto-approve for demo
    )
    await db.execute(stmt)
    await db.commit()
    return return_id

async def create_feedback(db: AsyncSession, user_id: str, order_id: str, rating: int, comment: str):
    stmt = insert(Feedback).values(
        user_id=user_id,
        order_id=order_id,
        rating=rating,
        comment=comment
    )
    await db.execute(stmt)
    await db.commit()
    return True



async def delete_chat_history(db: AsyncSession, user_id: str):
    """
    Hard deletes ONLY the chat history logs.
    Preserves Carts, Reservations, and Orders.
    """
    await db.execute(
        text("DELETE FROM chat_history WHERE user_id = :uid"),
        {"uid": user_id}
    )