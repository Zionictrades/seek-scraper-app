import os
import asyncpg
from typing import Optional

pool: Optional[asyncpg.pool.Pool] = None

async def init_db_pool():
    global pool
    dsn = os.getenv("DB_DSN")
    if not dsn:
        return
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)

async def close_db_pool():
    global pool
    if pool:
        await pool.close()

async def insert_lead(data):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO leads (dedupe_key, ad_url, role, company) VALUES ($1,$2,$3,$4)",
            data["dedupe_key"], data["ad_url"], data["role"], data.get("company")
        )