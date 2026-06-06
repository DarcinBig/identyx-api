"""
Gateway JWT middleware.

Single responsibility:
    - Intercept requests with Authorization: Bearer <token>
    - Validate the token via token-service (/tokens/verify)
    - Inject X-User-Id into the headers before forwarding

Public routes (no JWT required):
    - POST /auth/register
    - POST /auth/login
    - GET /health

All other routes require a valid JWT.
"""
import logging
import app.http as http_state

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("gateway.jwt")

# Routes that do not require JWT
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("GET", "/health"),
    ("GET", "/docs"),
    ("GET", "/redoc"),
    ("GET", "/openapi.json"),
}

def _is_public(method: str, path: str) -> bool:
    """Returns True if the given method is public."""
    return (method.upper(), path) in PUBLIC_ROUTES

def _extract_bearer_token(request: Request) -> str | None:
    """
    Extracts the token from the Authorization header.
    Expected format: "Bearer <token>"
    Returns None if absent or malformed.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):]
    return token if token else None

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware.

    For protected routes:
        1. Extract the Bearer token from the Authorization header
        2. Call token-service /tokens/verify
        3. If valid=True → inject X-User-Id into the headers
        4. If valid=False → return a 401 immediately

    The X-User-Id header is then read by the services
    via their get_current_user_id() dependency.
    """
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path

        # Public routes
        if _is_public(method, path):
            return await call_next(request)

        # Extract the token
        token = _extract_bearer_token(request)
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Missing or invalid Authorization header.",
                    "detail": "Expected: Authorization: Bearer <token>",
                }
            )

        # Validate via token-service
        if http_state.client is None:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Gateway not ready"},
            )

        try:
            verify_response = await http_state.client.post(
                f"{settings.token_service_url}/tokens/verify",
                json={"access_token": token},
                timeout=5.0,
            )
            verify_data = verify_response.json()
        except Exception as exc:
            logger.error("Token verification failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Token service unavailable"},
            )

        if not verify_data.get("valid"):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid or expired token."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Inject X-User-Id into the request headers
        user_id = verify_data.get("user_id")

        # Modify the request headers (Starlette scope)
        scope = request.scope
        headers = list(scope["headers"])

        # Delete X-User-Id if already present (security)
        headers = [
            (k ,v) for k, v in headers
            if k.lower() != b"x-user-id"
        ]
        headers.append((b"x-user-id", user_id.encode()))
        scope["headers"] = headers

        return await call_next(request)