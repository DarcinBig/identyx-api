"""
Shared fixtures for application-service tests.

- db_session  : in-memory async SQLAlchemy session (SQLite)
- fake_redis  : in-memory Redis (fakeredis)
- client      : httpx.AsyncClient for the FastAPI app
"""

import os

os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "identyx_applications")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")
os.environ.setdefault("REDIS_PASSWORD", "test-redis")

import fakeredis.aioredis as aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def fake_redis():
    """In-memory Redis for testing, wired into the cache module (Redis DB 3)."""
    import app.cache.redis as redis_cache

    redis = aioredis.FakeRedis(decode_responses=True)
    redis_cache._redis_client = redis
    yield redis
    redis_cache._redis_client = None
    await redis.flushall()
    await redis.aclose()


@pytest_asyncio.fixture(scope="function")
async def client(fake_redis, db_session):
    """HTTP client against the FastAPI app with an in-memory database + Redis."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as app_client:
        yield app_client

    app.dependency_overrides.clear()
