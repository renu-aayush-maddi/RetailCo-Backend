# scripts/check_db.py
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, future=True)

async def main():
    async with engine.begin() as conn:
        r = await conn.execute(text("select product_id, stock, reserved from inventory where product_id='P001'"))
        print(await r.fetchall())
        r2 = await conn.execute(text("select order_id, user_id, items, total_amount, status from orders order by created_at desc limit 5"))
        print(await r2.fetchall())

asyncio.run(main())
