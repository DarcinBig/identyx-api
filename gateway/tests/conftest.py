from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_rate_limit_redis():
    """
    Mock Redis for the rate limiter in all tests.
    The pipeline() method must return a mock with synchronous methods
    (zremrangebyscore, zadd, zcount) and an async execute().
    """
    with patch("app.middleware.rate_limit.get_rate_limit_redis") as mock_get:
        # Pipeline mock — used inside the async context
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock(return_value=0)
        mock_pipeline.zadd = MagicMock(return_value=1)
        mock_pipeline.zcount = MagicMock(return_value=0)   # count=0 → no rate limit
        mock_pipeline.execute = AsyncMock(return_value=[None, None, 0, None])
        # Context manager support (async)
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=None)

        # Redis client mock — pipeline() is synchronous
        mock_redis = MagicMock()
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        # Direct methods (if used without pipeline)
        mock_redis.zremrangebyscore = MagicMock(return_value=0)
        mock_redis.zadd = MagicMock(return_value=1)
        mock_redis.zcount = MagicMock(return_value=0)
        mock_redis.expire = MagicMock(return_value=True)
        # Context manager support (if used directly)
        mock_redis.__aenter__ = AsyncMock(return_value=mock_redis)
        mock_redis.__aexit__ = AsyncMock(return_value=None)

        mock_get.return_value = mock_redis
        yield mock_redis