from unittest.mock import patch

import fakeredis.aioredis as aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def fake_redis():
    """In-memory Redis for testing."""
    redis = aioredis.FakeRedis(decode_responses=True)
    yield redis
    await redis.flushall()
    await redis.aclose()

@pytest_asyncio.fixture
async def client(fake_redis):
    """HTTP client with Redis fakeredis."""
    with patch("app.cache.redis.get_redis", return_value=fake_redis):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as async_client:
            yield async_client