"""
Redis client for blacklisting access tokens.

Key: blacklist:{jti}
Value: "1"
TTL: Remaining token lifetime in seconds

When an access token is revoked, its JTI is blacklisted. Any verification checks Redis before accepting the token.
The key expires automatically—no manual cleanup is required.
"""
import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

_redis_client: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized. Must call init_redis() in lifespan first."
        )
    return _redis_client

async def init_redis() -> None:
    """Initialize the Redis client. Called in lifespan before get_redis()"""
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.get_redis_url(),
        encoding="utf-8",
        decode_responses=True,
    )
    await _redis_client.ping()

async def close_redis() -> None:
    """Close the Redis connection. Called in lifespan"""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None

async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    """
    Blacklists a JWT with a TTL.

    Args:
        jti: Unique identifier of the JWT
        ttl_seconds: Remaining lifetime in seconds
    """
    client = await get_redis()
    await client.set(
        f"blacklist:{jti}",
        1,
        ex=ttl_seconds,
    )

async def is_blacklisted(jti: str) -> bool:
    """Returns True if the JTI is blacklisted"""
    client = await get_redis()
    result = await client.get(f"blacklist:{jti}")
    return result is not None

