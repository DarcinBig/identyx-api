"""
Dynamic CORS middleware for the gateway (Sub-step D).

Replaces Starlette's static CORSMiddleware. Allowed origins are resolved per
request instead of from a fixed allow-list:

  - At CORS preflight (OPTIONS) no API key is presented — browsers never send
    X-Identyx-Key on OPTIONS. The gateway calls application-service
    `GET /applications/resolve-by-origin?origin=<origin>` (backed by a GIN
    index) to learn which active application(s) allow the origin, and returns
    the CORS headers when allowed. The API key is only validated on the actual
    request (see ApiKeyAuthMiddleware).
  - On the actual request the key has already been validated, and
    ApiKeyAuthMiddleware injects `scope["application_allowed_origins"]` from
    the verify-key response. When present we use it; otherwise we fall back to
    the static `CORS_ORIGINS` gateway setting.

Static origins from `CORS_ORIGINS` are always allowed, in every environment.
"""

import logging

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import app.http as http_state
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("gateway.dynamic_cors")

_ALLOW_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
_ALLOW_HEADERS = "Authorization, Content-Type, Accept, Origin, X-Identyx-Key"
_EXPOSE_HEADERS = "X-Request-Id, Retry-After"
_MAX_AGE = 600


def _normalize_origin(origin: str) -> str:
    return origin.rstrip("/")


def _static_origins() -> set[str]:
    return {_normalize_origin(o) for o in settings.get_cors_origins_list()}


def _is_static_origin(origin: str) -> bool:
    return _normalize_origin(origin) in _static_origins()


async def _resolve_by_origin(origin: str) -> bool:
    """Ask application-service whether any active app allows this origin."""
    if http_state.client is None:
        logger.warning("gateway client not ready during CORS resolution")
        return False
    try:
        resp = await http_state.client.get(
            f"{settings.application_service_url}/applications/resolve-by-origin",
            params={"origin": origin},
            headers={"X-Internal-Key": settings.internal_api_key},
            timeout=3.0,
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("allowed"))
    except Exception as exc:
        logger.warning("resolve-by-origin error: %s", exc)
        return False


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Resolves CORS per-origin instead of a static allow-list.

    Wraps the whole inner app, so OPTIONS preflights are answered here before
    any auth middleware runs (browsers never send credentials/keys on
    preflight). For actual requests the response is produced by the inner
    chain first; the resolved per-app origins (written into `request.scope` by
    ApiKeyAuthMiddleware while the request travels down) are read afterwards,
    because they share the same scope dict.
    """

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if not origin:
            return await call_next(request)

        if request.method.upper() == "OPTIONS":
            return await self._handle_preflight(request, origin)

        return await self._handle_actual(request, call_next, origin)

    async def _handle_preflight(self, request: Request, origin: str):
        if _is_static_origin(origin) or await _resolve_by_origin(origin):
            return self._preflight_response(origin)
        logger.info(
            "CORS preflight disallowed",
            extra={"origin": origin, "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Disallowed CORS origin."},
        )

    @staticmethod
    def _preflight_response(origin: str) -> Response:
        return Response(
            status_code=status.HTTP_200_OK,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Vary": "Origin",
                "Access-Control-Allow-Methods": _ALLOW_METHODS,
                "Access-Control-Allow-Headers": _ALLOW_HEADERS,
                "Access-Control-Expose-Headers": _EXPOSE_HEADERS,
                "Access-Control-Max-Age": str(_MAX_AGE),
                "Content-Length": "0",
            },
        )

    async def _handle_actual(self, request: Request, call_next, origin: str):
        response = await call_next(request)

        app_origins = request.scope.get("application_allowed_origins")
        if app_origins is None:
            # No API-key context — fall back to the static CORS_ORIGINS list.
            app_origins = settings.get_cors_origins_list()

        allowed = _is_static_origin(origin) or _normalize_origin(origin) in {
            _normalize_origin(o) for o in app_origins
        }

        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response
