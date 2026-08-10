"""
FastAPI dependencies for the auth service.

`get_current_user_id()` reads the X-User-Id header
injected by the gateway after JWT validation.

Services never validate the JWT themselves —
that's the exclusive role of the gateway and token service.
"""
from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


def get_current_user_id(request: Request) -> str:
    """
    Extracts the logged-in user's ID from the X-User-Id header.

    This header is injected by the gateway after JWT validation.
    If absent → 401 (request not passed through the gateway or invalid token).

    Usage in a route:
        @router.post("/logout")
        async def logout(
        user_id: str = Depends(get_current_user_id),
        ...
        ):
    """
    user_id = request.headers.get("X-User-Id", "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


async def require_internal_key(
    x_internal_key: str | None = Header(default=None),
) -> None:
    """
    Protects the privileged internal endpoints (e.g. /auth/internal/verify-password).
    Only callers that know the shared secret may invoke them.

    Fails closed: if the secret is not configured, access is denied.
    """
    settings = get_settings()
    expected = settings.internal_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API key not configured.",
        )
    if x_internal_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key.",
        )
