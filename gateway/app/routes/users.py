from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
import httpx
import app.http as http_state

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/users", tags=["users"])

async def _proxy(request: Request, path: str) -> JSONResponse:
    """Forward to user-service"""
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    target_url = f"{settings.user_service_url}{path}"
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
            content={"error": "User service timeout"},
        )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "User service unavailable"},
        )

@router.post("/", operation_id="create")
async def create_user(request: Request):
    """POST /users -> user-service"""
    return await _proxy(request, "/users")

@router.get("/me", operation_id="me")
async def get_me(request: Request):
    """GET /users/me -> user-service"""
    return await _proxy(request, "/users/me")

@router.get("/internal/by-email", operation_id="get-user-by-email")
async def get_user_by_email(request: Request):
    """GET /internal/by-email -> user-service"""
    return await _proxy(request, "/users/internal/by-email")

@router.get("/{user_id}", operation_id="user-id")
async def get_user(request: Request, user_id: str):
    """GET /users/{user_id} -> user-service"""
    return await _proxy(request, f"/users/{user_id}")

@router.patch("/{user_id}", operation_id="update")
async def update_user(request: Request, user_id: str):
    """PATCH /users/{user_id} -> user-service"""
    return await _proxy(request, f"/users/{user_id}")

@router.delete("/{user_id}", operation_id="delete")
async def delete_user(request: Request, user_id: str):
    """DELETE /users/{user_id} -> user-service"""
    return await _proxy(request, f"/users/{user_id}")

@router.post("/{user_id}/avatar", operation_id="upload-avatar")
async def upload_avatar(request: Request, user_id: str):
    return await _proxy(request, f"/users/{user_id}/avatar")


@router.get("/{user_id}/avatar", operation_id="avatar-url")
async def get_avatar(request: Request, user_id: str):
    return await _proxy(request, f"/users/{user_id}/avatar")


@router.delete("/{user_id}/avatar", operation_id="reset-avatar")
async def delete_avatar(request: Request, user_id: str):
    return await _proxy(request, f"/users/{user_id}/avatar")



