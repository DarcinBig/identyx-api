# This router receives all /auth/* requests and forwards them to auth-service
import httpx
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

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
            content={"error": "Auth service timeout"},
        )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
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
    """
    The gateway extracts the access token from the Authorization header
    and injects it into the body before forwarding it to the auth-service.
    This allows the auth-service to revoke the access token in Redis.

    POST /auth/logout -> auth-service
    """

    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )

    # Read the original body (contains refresh_token)
    body_bytes = await request.body()

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "content-length")
    }

    # try:
    #     body = json_lib.loads(body_bytes) if body_bytes else {}
    # except Exception:
    #     body = {}

    # Extract the access token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[len("Bearer "):]
        if access_token.strip():
            headers["x-access-token"] = access_token.strip()
            print(f"[gateway/logout] X-Access-Token injected: {access_token[:30]}...")

    # Rebuild the enriched body
    # enriched_body = json_lib.dumps(body).encode("utf-8")

    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/logout",
            content=body_bytes,
            headers=headers,
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
            content={"error": "Auth service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Auth service unavailable"},
        )

@router.post("/refresh", operation_id="refresh-token")
async def refresh(request: Request):
    """POST /auth/refresh -> auth-service"""
    return await _proxy(request, "/auth/refresh")

@router.get("/verify-email", operation_id="verify-email")
async def verify_email(request: Request):
    """
    GET /auth/verify-email -> auth-service
    Public route — no JWT required.
    The token is passed as a query param: ?token=xxx
    """
    return await _proxy(request, "/auth/verify-email")