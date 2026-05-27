# This router receives all /auth/* requests and forwards them to auth-service
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import httpx

import app.http as http_state

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

async def _proxy(request: Request, path: str) -> JSONResponse:
    """
    A utility function shared by all routes on the router.

    It:
        1. Reads the body of the incoming request
        2. Retrieves the headers (Content-Type forwarder, Authorization, etc.)
        3. Sends the request to the target service via HTTPX
        4. Returns the service's response to the client as is

    In case of a network error (service down, timeout), returns a 503.
    :param request:
    :param path:
    :return:
    """
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    target_url = f"{settings.auth_service_url}{path}"

    # Read the body (may be empty on GET)
    body = await request.body()

    # Filter the headers to forward
    # We exclude 'host' because it belongs to the gateway, not the target service
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
            headers=dict(response.headers),
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"error": "Auth service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "Auth service unavailable"},
        )

@router.post("/register", operation_id="register")
async def register(request: Request):
    """POST /auth/register -> auth-service"""
    return await _proxy(request, "/auth/register")

@router.post("/login", operation_id="login")
async def login(request: Request):
    """POST /auth/login -> auth-service"""
    return await _proxy(request, "/auth/login")

@router.post("/logout", operation_id="logout")
async def logout(request: Request):
    """POST /auth/logout -> auth-service"""
    return await _proxy(request, "/auth/logout")

@router.post("/refresh", operation_id="refresh-token")
async def refresh(request: Request):
    """POST /auth/refresh -> auth-service"""
    return await _proxy(request, "/auth/refresh")