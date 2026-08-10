import httpx
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

import app.http as http_state
from app.core.config import get_settings
from app.deps import bearer_scheme

settings = get_settings()
router = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=[Depends(bearer_scheme)])


async def _proxy(request: Request, path: str) -> JSONResponse:
    """Forward to session-service"""
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )

    target_url = f"{settings.session_service_url}{path}"
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "content-length")
    }

    try:
        response = await http_state.client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )

        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from service"}

        return JSONResponse(
            content=content,
            status_code=response.status_code,
        )

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Session service timeout"},
        )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Session service unavailable"},
        )

@router.get("/", operation_id="index")
@router.get("", operation_id="index-no-slash", include_in_schema=False)
async def list_sessions(request: Request):
    """
    List the active sessions of the authenticated user.

    **Auth** — `Authorization: Bearer <access_token>`.

    The gateway resolves the user id from the token and forwards it to the
    session-service — the caller never provides it.

    **Success** `200` — `{total, sessions: [...]}`.
    **Errors** — `401` missing/invalid/expired token.
    """
    return await _proxy(request, "/sessions/")

@router.delete("/revoke-all", operation_id="revoke-all")
async def revoke_all_sessions(request: Request):
    """
    Revoke every session of the authenticated user (sign out everywhere).

    **Auth** — `Authorization: Bearer <access_token>`.

    **Success** `200` — confirmation with the number of revoked sessions.
    **Errors** — `401`.
    """
    return await _proxy(request, "/sessions/revoke-all")

@router.delete("/{session_id}", operation_id="delete")
async def delete_session(request: Request, session_id: str):
    """
    Revoke a single session.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Path params** — `session_id`: UUID of the session.
    Only sessions owned by the authenticated user can be revoked (`403`).

    **Success** `200`.
    **Errors** — `401`, `403` not the owner, `404` session not found.
    """
    return await _proxy(request, f"/sessions/{session_id}")