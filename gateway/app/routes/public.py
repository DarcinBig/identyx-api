"""
Public API key introspection routes.

Proxy routes for third-party applications presenting an API key.
These routes are authenticated by API key only (no JWT required).

    GET /v1/public/applications/me → application-service GET /applications/me
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import app.http as http_state
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("gateway.public")

router = APIRouter(prefix="/public", tags=["public"])


@router.get(
    "/applications/me",
    summary="Non-sensitive metadata for the presented API key",
    operation_id="public_applications_me",
    include_in_schema=False,
)
async def public_applications_me(request: Request):
    """
    Returns non-sensitive metadata of the application associated with the
    presented `X-Identyx-Key`: application_id, name, allowed_origins, status,
    key_type.

    Authenticated by API key only — no JWT required.
    """
    if http_state.client is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Gateway not ready"},
        )

    try:
        response = await http_state.client.get(
            f"{settings.application_service_url}/applications/me",
            headers={
                "X-Internal-Key": settings.internal_api_key,
                "X-Identyx-Key": request.headers.get("x-identyx-key", ""),
            },
            timeout=5.0,
        )
        return JSONResponse(
            status_code=response.status_code,
            content=response.json(),
        )
    except Exception as exc:
        logger.error("Failed to proxy to application-service: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": "Application service unavailable"},
        )
