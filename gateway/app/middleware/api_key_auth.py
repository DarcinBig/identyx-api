"""
Gateway API key authentication middleware.

Single responsibility:
    - Intercept requests with X-Identyx-Key header
    - Resolve the key via application-service /applications/verify-key
    - Inject X-Tenant-Id + X-Application-Id into the request headers
    - Skip JWT validation for routes that only need API key auth

Public API key routes (no JWT required):
    - GET /v1/public/applications/me

All other routes with an API key also get tenant context injected,
but still require JWT for user identity (handled by JWTAuthMiddleware).

Resolution is cache-first: application-service caches results in Redis DB 3
with a 60s TTL. Active invalidation on key revocation.
"""
import logging

import httpx
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import app.http as http_state
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("gateway.api_key_auth")

# Routes that require API key but NOT JWT.
# The public API is versioned under /v1.
API_KEY_ONLY_ROUTES: set[tuple[str, str]] = {
    ("GET", "/v1/public/applications/me"),
}


def _is_api_key_only(method: str, path: str) -> bool:
    normalized = path.rstrip("/") if path != "/" else "/"
    return (method.upper(), normalized) in API_KEY_ONLY_ROUTES


def _extract_api_key(request: Request) -> str | None:
    """Extracts the full key from the X-Identyx-Key header."""
    key = request.headers.get("x-identyx-key", "")
    return key if key else None


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    API key authentication middleware.

    For requests with X-Identyx-Key:
        1. Extract the full key
        2. Call application-service /applications/verify-key
        3. If valid: inject X-Tenant-Id + X-Application-Id
        4. If invalid: return 401 immediately

    For requests without X-Identyx-Key:
        - Pass through to the next middleware (JWTAuth or routes)
    """

    async def dispatch(self, request: Request, call_next):
        full_key = _extract_api_key(request)

        # No API key presented — pass through to JWT or public routes
        if not full_key:
            return await call_next(request)

        # Validate via application-service
        if http_state.client is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Gateway not ready"},
            )

        try:
            verify_response = await http_state.client.post(
                f"{settings.application_service_url}/applications/verify-key",
                json={"key_id": full_key, "secret": full_key},
                headers={"X-Internal-Key": settings.internal_api_key},
                timeout=5.0,
            )
        except httpx.ConnectError:
            logger.error("Application service unavailable")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Application service unavailable"},
            )
        except httpx.TimeoutException:
            logger.error("Application service timeout on verify-key")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Application service timeout"},
            )

        if verify_response.status_code != 200:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid API key."},
            )

        try:
            verify_data = verify_response.json()
        except Exception:
            logger.error("Invalid response from application-service verify-key")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Invalid application-service response"},
            )

        tenant_id = verify_data.get("tenant_id")
        application_id = verify_data.get("application_id")

        if not tenant_id or not application_id:
            logger.error(
                "verify-key returned incomplete data: %s", verify_data
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Incomplete application-service response"},
            )

        # Inject resolved context into request headers
        scope = request.scope
        headers = list(scope["headers"])

        # Strip caller-controlled security-sensitive headers (defense in depth)
        blocked = {b"x-tenant-id", b"x-application-id", b"x-internal-key"}
        headers = [
            (k, v) for k, v in headers
            if k.lower() not in blocked
        ]
        headers.append((b"x-tenant-id", tenant_id.encode()))
        headers.append((b"x-application-id", application_id.encode()))
        scope["headers"] = headers

        # Per-app allowed origins for dynamic CORS (Sub-step D). The key is
        # already validated; store what the app is allowed to use so
        # DynamicCORSMiddleware can inject Access-Control-Allow-Origin.
        scope["application_allowed_origins"] = list(
            verify_data.get("allowed_origins") or []
        )

        # Mark as API-key-authenticated so JWT middleware can skip
        # validation for API-key-only routes.
        scope["api_key_authenticated"] = True

        logger.debug(
            "API key resolved: tenant_id=%s application_id=%s",
            tenant_id,
            application_id,
        )

        return await call_next(request)
