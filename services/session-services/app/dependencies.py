from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


def get_current_user_id(request: Request) -> str:
    """
    Extracts the logged-in user's ID from the X-User-Id header.
    Injected by the gateway after JWT validation.
    """
    user_id = request.headers.get("X-User-Id", "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WW-Authenticate": "Bearer"},
        )
    return user_id


async def require_internal_key(
    x_internal_key: str | None = Header(default=None),
) -> None:
    """
    Protects the internal session endpoints.
    Only the auth-service (which knows the shared secret) may call them.
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