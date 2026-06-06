from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import httpx
import app.http as http_state

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/sessions", tags=["sessions"])


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
async def list_sessions(request: Request):
    """GET /sessions → session-service"""
    return await _proxy(request, "/sessions/")

@router.get("/{session_id}", operation_id="session-id")
async def get_session(request: Request, session_id: str):
    """GET /sessions/{session_id} → session-service"""
    return await _proxy(request, f"/sessions/{session_id}")

@router.delete("/revoke-all", operation_id="revoke-all")
async def revoke_all_sessions(request: Request):
    """DELETE /sessions/revoke-all → session-service"""
    return await _proxy(request, "/sessions/revoke-all")

@router.delete("/{session_id}", operation_id="delete")
async def delete_session(request: Request, session_id: str):
    """DELETE /sessions/{session_id} → session-service"""
    return await _proxy(request, f"/sessions/{session_id}")