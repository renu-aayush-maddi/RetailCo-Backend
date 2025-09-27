# # backend/models.py
# from sqlalchemy import Column, Integer, String, Numeric, JSON, TIMESTAMP, func
# from backend.db import Base


# class Product(Base):
#     __tablename__ = "products"
#     product_id = Column(String, primary_key=True, index=True)
#     name = Column(String, nullable=False)
#     category = Column(String, index=True)
#     price = Column(Numeric(10,2), nullable=False)
#     images = Column(JSON)
#     attributes = Column(JSON)
#     tags = Column(JSON)
#     created_at = Column(TIMESTAMP, server_default=func.now())

# class Inventory(Base):
#     __tablename__ = "inventory"
#     inventory_id = Column(Integer, primary_key=True, autoincrement=True)
#     product_id = Column(String, nullable=False, index=True)
#     store_id = Column(String, index=True)
#     stock = Column(Integer, default=0)
#     reserved = Column(Integer, default=0)
#     last_updated = Column(TIMESTAMP, server_default=func.now())

# class User(Base):
#     __tablename__ = "users"
#     user_id = Column(String, primary_key=True)
#     name = Column(String)
#     phone = Column(String)
#     email = Column(String)
#     loyalty_tier = Column(String)
#     meta = Column(JSON)

# class Order(Base):
#     __tablename__ = "orders"
#     order_id = Column(String, primary_key=True)
#     user_id = Column(String)
#     items = Column(JSON)
#     total_amount = Column(Numeric(10,2))
#     status = Column(String)
#     fulfillment = Column(String)
#     created_at = Column(TIMESTAMP, server_default=func.now())







# backend/models.py
from sqlalchemy import Column, Integer, String, Numeric, JSON, TIMESTAMP, func, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from .db import Base
import uuid

def gen_uuid():
    return str(uuid.uuid4())

class Product(Base):
    __tablename__ = "products"
    product_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, index=True)
    price = Column(Numeric(10,2), nullable=False)
    images = Column(JSON)
    attributes = Column(JSON)
    tags = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Inventory(Base):
    __tablename__ = "inventory"
    inventory_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    store_id = Column(String, index=True)
    stock = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    last_updated = Column(TIMESTAMP, server_default=func.now())

class User(Base):
    __tablename__ = "users"
    user_id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone_number = Column(String, nullable=True, unique=True)
    telegram_id = Column(String, nullable=True, unique=True)
    loyalty_tier = Column(String)
    meta = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    items = Column(JSON)
    total_amount = Column(Numeric(10,2))
    status = Column(String)
    fulfillment = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.now())

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    session_id = Column(String, index=True)
    role = Column(String)  # "user" | "assistant"
    message = Column(Text)
    intent = Column(String, nullable=True)
    results = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
