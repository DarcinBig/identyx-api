from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_internal_key(
    x_internal_key: str | None = Header(default=None),
) -> None:
    """
    Protects every /applications/* endpoint of this service.

    application-service is an internal service — none of its routes are ever
    exposed directly to clients (they go through the gateway, which adds the
    shared `X-Internal-Key` header). This includes `/applications/verify-key`
    (used by the gateway on every request) and `/applications/me` (proxied
    publicly as `GET /v1/public/applications/me`).

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
