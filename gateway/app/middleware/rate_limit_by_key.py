"""
Per-route-group (API key) rate limiting for the gateway.

Complements the existing per-IP limiter (`app.middleware.rate_limit`). Once
ApiKeyAuthMiddleware has resolved the presented API key, this middleware
enforces a requests-per-minute budget per route group — identified by the
resolved `application_id` and the URL path — in parallel with the IP-based
limit.  A single app hitting `/v1/auth/login`, `/v1/users/me` and
`/v1/sessions` gets three independent 600/min buckets, so abuse on one
endpoint never starves the others.

Sliding window over Redis DB 2 (same instance as the IP limiter), key:
    ratekey:{application_id}:{path_group}

Fails open on Redis unavailability, matching the IP limiter behaviour.
"""

import logging
import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.middleware import rate_limit

settings = get_settings()
logger = logging.getLogger("gateway.rate_limit_by_key")


def _get_application_id(scope) -> str | None:
    headers = dict(scope.get("headers", []))
    value = headers.get(b"x-application-id")
    if not value:
        return None
    try:
        decoded = value.decode()
    except Exception:
        return None
    return decoded or None


class RateLimitByKeyMiddleware(BaseHTTPMiddleware):
    """Rate limits by resolved application (API key), after key validation."""

    async def dispatch(self, request: Request, call_next):
        # Only requests authenticated by an API key get a per-application
        # budget. IP-based limiting covers the rest.
        if not request.scope.get("api_key_authenticated"):
            return await call_next(request)

        application_id = _get_application_id(request.scope)
        if not application_id:
            return await call_next(request)

        path = request.scope.get("path", "")
        limit = settings.rate_limit_per_key_rpm
        window_seconds = 60
        path_group = path.replace("/", "_").strip("_") or "root"
        key = f"ratekey:{application_id}:{path_group}"

        try:
            redis = await rate_limit.get_rate_limit_redis()
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
                    "Rate limit exceeded by key: app=%s path=%s count=%d limit=%d",
                    application_id, path, count, limit,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Too many requests.",
                        "detail": f"Limit: {limit} requests per minute.",
                        "retry_after": window_seconds,
                    },
                    headers={"Retry-After": str(window_seconds)},
                )
        except Exception as exc:
            logger.warning("Rate limit by key Redis unavailable: %s", exc)

        return await call_next(request)