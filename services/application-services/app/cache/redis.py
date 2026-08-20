"""
Redis cache for API-key → tenant resolution.

Dedicated DB 3 (not mixed with DB 0 blacklist / DB 1 state / DB 2 rate-limit).

Key:   apikey:{key_id}
Value: JSON {tenant_id, application_id, key_type, allowed_origins, status}
TTL:   api_key_cache_ttl_seconds (default 60)

Freshness model (PRD §5.4):
  - Active invalidation on revocation: DEL apikey:{key_id} issued at revoke
    time — the TTL is only a safety net, not the primary freshness mechanism.
  - The service must stay correct even if Redis is down: callers degrade to
    the DB and treat cache errors as non-fatal.
"""

import json
import logging

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger("application-service.cache")

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized. Must call init_redis() in lifespan first."
        )
    return _redis_client


async def init_redis() -> None:
    """Initialize the Redis client. Called in lifespan before get_redis()."""
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.get_redis_url(),
        encoding="utf-8",
        decode_responses=True,
    )
    await _redis_client.ping()


async def close_redis() -> None:
    """Close the Redis connection. Called in lifespan."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


def _cache_key(key_id: str) -> str:
    return f"apikey:{key_id}"


async def get_cached_resolution(key_id: str) -> dict | None:
    """Returns the cached resolution dict, or None on miss/error."""
    try:
        client = await get_redis()
        raw = await client.get(_cache_key(key_id))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("cache_get_failed", extra={"key_id": key_id, "error": str(exc)})
        return None


async def set_cached_resolution(key_id: str, payload: dict) -> None:
    """Stores a resolution with the configured TTL. Errors are non-fatal."""
    try:
        client = await get_redis()
        await client.set(
            _cache_key(key_id),
            json.dumps(payload),
            ex=settings.api_key_cache_ttl_seconds,
        )
    except Exception as exc:
        logger.warning("cache_set_failed", extra={"key_id": key_id, "error": str(exc)})


async def invalidate_key(key_id: str) -> None:
    """Actively deletes a resolution. Errors are non-fatal (TTL is the backup)."""
    try:
        client = await get_redis()
        await client.delete(_cache_key(key_id))
    except Exception as exc:
        logger.warning("cache_invalidate_failed", extra={"key_id": key_id, "error": str(exc)})
