from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_internal_key(
    x_internal_key: str | None = Header(default=None),
) -> None:
    """
    Protects the privileged token endpoints (/tokens/generate, /tokens/revoke).
    Only the auth-service (which knows the shared secret) may call them.
    /tokens/verify stays open — the gateway needs it for every request.

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
