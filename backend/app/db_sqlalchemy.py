import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

dsn = os.getenv("DB_DSN")  # postgres+asyncpg://...
engine = None
AsyncSessionLocal = None

if dsn:
    engine = create_async_engine(dsn, pool_size=10, max_overflow=0)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)