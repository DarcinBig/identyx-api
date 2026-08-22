"""
Redis-based rate limiting — sliding window algorithm.
Pure ASGI implementation for maximum compatibility.

Principle:
    - Redis key: rate:{ip}:{path_group}
    - Store the timestamp of each request in a sorted set
    - Delete entries older than the window size
    - If the count exceeds the limit → 429 Too Many Requests error

Path groups and their limits:
    - /auth/login → 10 req/min
    - /auth/register → 5 req/min
    - /auth/reset-password → 3 req/min
    - /auth/verify-email + resend → 5 req/min
    - /auth/refresh → 20 req/min
    - /sessions/* → 60 req/min
    - all other groups → 100 req/min (global)
"""
import json
import logging
import time

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("gateway.rate_limit")

_redis: aioredis.Redis | None = None


async def get_rate_limit_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        logger.info("Connecting to Redis: %s", settings.rate_limit_redis_url[:30])
        _redis = aioredis.from_url(
            settings.rate_limit_redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


def _get_limit_for_path(path: str) -> int:
    if path in ("/v1/auth/login", "/auth/login"):
        return settings.rate_limit_login
    if path in ("/v1/auth/register", "/auth/register"):
        return settings.rate_limit_register
    if path in ("/v1/auth/reset-password", "/auth/reset-password"):
        return settings.rate_limit_reset_password
    if path in ("/v1/auth/verify-email", "/auth/verify-email",
                "/v1/auth/resend-verification", "/auth/resend-verification"):
        return settings.rate_limit_verify_email
    if path in ("/v1/auth/refresh", "/auth/refresh"):
        return settings.rate_limit_refresh
    if path.startswith("/v1/sessions") or path.startswith("/sessions"):
        return settings.rate_limit_sessions
    return settings.rate_limit_global


def _get_client_ip(scope) -> str:
    # When behind a trusted proxy the real client IP is in X-Forwarded-For;
    # otherwise we must ignore it (attacker-controlled) and use the direct
    # peer address to prevent brute-force bypass via spoofed headers.
    if settings.trust_proxy:
        headers = dict(scope.get("headers", []))
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        if forwarded:
            return forwarded.split(",")[0].strip()
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


class RateLimitMiddleware:
    """Rate limiting ASGI pur — sliding window Redis."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        ip = _get_client_ip(scope)
        limit = _get_limit_for_path(path)
        window_seconds = 60

        path_group = path.replace("/", "_").strip("_") or "root"
        key = f"rate:{ip}:{path_group}"

        try:
            redis = await get_rate_limit_redis()
            now = time.time()
            window_start = now - window_seconds

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, window_seconds)
            results = await pipe.execute()

            count = results[2]

            if count > limit:
                logger.warning(
                    "Rate limit exceeded: ip=%s path=%s count=%d limit=%d",
                    ip, path, count, limit
                )
                body = json.dumps({
                    "error": "Too many requests.",
                    "detail": f"Limit: {limit} requests per minute.",
                    "retry_after": window_seconds,
                }).encode()

                await send({
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(window_seconds).encode()),
                        (b"content-length", str(len(body)).encode()),
                    ],
                })
                await send({
                    "type": "http.response.body",
                    "body": body,
                })
                return

        except Exception as exc:
            logger.warning("Rate limit Redis unavailable: %s", exc)

        await self.app(scope, receive, send)