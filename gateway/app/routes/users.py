from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx

from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/users", tags=["users"])

async def _proxy(request: Request, path: str) -> JSONResponse:
    """Forward to user-service"""
    from app.main import http_client

    target_url = f"{settings.user_service_url}{path}"
    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "content-length")
    }

    try:
        response = await http_client.request(
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
            content={"error": "User service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=503,
            content={"error": "User service unavailable"},
        )

@router.get("/me", operation_id="me")
async def get_me(request: Request):
    """GET /users/me -> user-service"""
    return await _proxy(request, "/users/me")

@router.get("/{user_id}", operation_id="user-id")
async def get_user(request: Request, user_id: str):
    """GET /users/{user_id} -> user-service"""
    return await _proxy(request, f"/users/{user_id}")

@router.post("/", operation_id="create")
async def create_user(request: Request):
    """POST /users -> user-service"""
    return await _proxy(request, "/users")

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



