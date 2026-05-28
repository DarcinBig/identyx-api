from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import httpx
import app.http as http_state

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/tokens", tags=["tokens"])

async def _proxy(request: Request, path: str) -> JSONResponse:
    """Forward to token-service"""
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )

    target_url = f"{settings.token_service_url}{path}"
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
        return JSONResponse(
            content=response.json() if response.content else None,
            status_code=response.status_code,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"error": "Token service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "Token service unavailable"},
        )

@router.post("/generate", operation_id="generate")
async def generate_token(request: Request):
    """POST /tokens/generate → token-service"""
    return await _proxy(request, "/tokens/generate")

@router.post("/verify", operation_id="verify")
async def verify_token(request: Request):
    """POST /tokens/verify → token-service"""
    return await _proxy(request, "/tokens/verify")

@router.post("/revoke", operation_id="revoke-token")
async def revoke_token(request: Request):
    """POST /tokens/revoke → token-service"""
    return await _proxy(request, "/tokens/revoke")