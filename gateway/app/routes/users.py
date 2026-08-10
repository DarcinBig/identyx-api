import logging

import httpx
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

import app.http as http_state
from app.core.config import get_settings
from app.deps import bearer_scheme

logger = logging.getLogger("gateway.users")
settings = get_settings()
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(bearer_scheme)])

async def _confirm_password(user_id: str, password: str) -> bool:
    """
    Confirms the account password via auth-service (internal endpoint).

    Required before destructive operations (delete account, delete avatar)
    so a stolen access token alone cannot destroy a profile.
    """
    if http_state.client is None:
        return False
    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/internal/verify-password",
            json={"user_id": user_id, "password": password},
            headers={"X-Internal-Key": settings.internal_api_key} if settings.internal_api_key else {},
            timeout=10.0,
        )
        data = response.json()
        return bool(data.get("valid"))
    except Exception as exc:
        logger.error("password_confirmation_failed", extra={"error": str(exc)})
        return False


async def _read_confirmation_password(request: Request) -> str | None:
    """Extracts the `password` field from a JSON body. None if missing/invalid JSON."""
    try:
        body = await request.json()
    except Exception:
        return None
    password = body.get("password")
    return password if isinstance(password, str) and password else None

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

@router.get("/me", operation_id="me")
async def get_me(request: Request):
    """
    Return the profile of the authenticated user.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Success** `200` — full user object `{id, email, username, is_verified, ...}`.
    **Errors** — `401` missing/invalid/expired token.
    """
    return await _proxy(request, "/users/me")

@router.get("/{user_id}", operation_id="user-id")
async def get_user(request: Request, user_id: str):
    """
    Return a user profile.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner (or the user themselves) can read the
    profile. A different account gets `403`.

    **Path params** — `user_id`: UUID of the user.

    **Success** `200` — user object.
    **Errors** — `401` no/invalid token, `403` not the owner, `404` not found.
    """
    return await _proxy(request, f"/users/{user_id}")

@router.patch("/{user_id}", operation_id="update")
async def update_user(request: Request, user_id: str):
    """
    Update the profile (partial update).

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner can update (`403` otherwise).

    **Path params** — `user_id`: UUID of the user.
    **Body** `application/json` (at least one field):
    ```json
    { "username": "new_username", "first_name": "Ada", "last_name": "Lovelace" }
    ```

    **Success** `200` — updated user object.
    **Errors** — `401`, `403`, `404`, `422` invalid body.
    """
    return await _proxy(request, f"/users/{user_id}")

@router.delete("/{user_id}", operation_id="delete")
async def delete_user(request: Request, user_id: str):
    """
    Permanently delete the account and revoke all sessions.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner can delete (`403` otherwise).

    **Password confirmation** — the current password must be provided in
    the body. It is verified by the auth-service (Argon2id) before the
    profile is deleted. Wrong password → `403`.

    **Path params** — `user_id`: UUID of the user.
    **Body** `application/json`:
    ```json
    { "password": "<current_password>" }
    ```

    **Success** `200` — deletion confirmation.
    **Errors** — `401`, `403`, `404`, `422`.
    """
    password = await _read_confirmation_password(request)
    if not password:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Password confirmation is required."},
        )
    if not await _confirm_password(user_id, password):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Invalid password. Account not deleted."},
        )
    return await _proxy(request, f"/users/{user_id}")

@router.post("/{user_id}/avatar", operation_id="upload-avatar")
async def upload_avatar(request: Request, user_id: str):
    """
    Upload (or replace) the user's avatar image.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Path params** — `user_id`: UUID of the user.
    **Body** `multipart/form-data` — field `file` (image; PNG/JPEG).

    **Success** `200` — `{avatar_url, message}`.
    **Errors** — `401`, `403`, `422` invalid file.
    """
    return await _proxy(request, f"/users/{user_id}/avatar")


@router.get("/{user_id}/avatar", operation_id="avatar-url")
async def get_avatar(request: Request, user_id: str):
    """
    Return the current avatar URL for a user.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Path params** — `user_id`: UUID of the user.

    **Success** `200` — `{avatar_url}` (null when no avatar is set).
    **Errors** — `401`, `403`.
    """
    return await _proxy(request, f"/users/{user_id}/avatar")


@router.delete("/{user_id}/avatar", operation_id="reset-avatar")
async def delete_avatar(request: Request, user_id: str):
    """
    Remove the user's avatar (fallback to the default).

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner can reset (`403` otherwise).

    **Password confirmation** — the current password must be provided in
    the body. It is verified by the auth-service before the avatar is
    removed. Wrong password → `403`.

    **Path params** — `user_id`: UUID of the user.
    **Body** `application/json`:
    ```json
    { "password": "<current_password>" }
    ```

    **Success** `200` — confirmation.
    **Errors** — `401`, `403`, `422`.
    """
    password = await _read_confirmation_password(request)
    if not password:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Password confirmation is required."},
        )
    if not await _confirm_password(user_id, password):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Invalid password. Avatar not reset."},
        )
    return await _proxy(request, f"/users/{user_id}/avatar")

@router.post("/{user_id}/deletion-request", operation_id="deletion-request")
async def create_deletion_request(request: Request, user_id: str):
    """
    Start a GDPR account deletion.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner can request the deletion (`403` otherwise).

    **Password confirmation** — the current password must be provided in
    the body. It is verified by the auth-service (Argon2id) before the
    request is created. Wrong password → `403`.

    Sends a confirmation email containing a one-time deletion link.
    The account is only erased once the link has been confirmed
    (`POST /auth/confirm-deletion`), which proves the owner controls
    the email address (GDPR explicit confirmation).

    **Path params** — `user_id`: UUID of the user.
    **Body** `application/json`:
    ```json
    { "password": "<current_password>" }
    ```

    **Success** `200` — confirmation message.
    **Errors** — `401`, `403`, `404`, `422`.
    """
    # Ownership check — the caller must be the account owner
    current_user_id = request.headers.get("X-User-Id", "")
    if not current_user_id or current_user_id != user_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "You can only request deletion for your own account."},
        )

    password = await _read_confirmation_password(request)
    if not password:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Password confirmation is required."},
        )
    if not await _confirm_password(user_id, password):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Invalid password. Deletion request not created."},
        )

    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/internal/deletion-request",
            json={"user_id": user_id},
            headers={"X-Internal-Key": settings.internal_api_key} if settings.internal_api_key else {},
            timeout=10.0,
        )
        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from auth service"}
        return JSONResponse(content=content, status_code=response.status_code)
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

@router.post("/{user_id}/email-change", operation_id="email-change")
async def request_email_change(request: Request, user_id: str):
    """
    Start an email address change.

    **Auth** — `Authorization: Bearer <access_token>`.

    **Ownership** — only the owner can change the email (`403` otherwise).

    **Password confirmation** — the current password must be provided in
    the body. It is verified by the auth-service (Argon2id) before the
    request is created. Wrong password → `403`.

    Sends a confirmation email to the NEW address. The email is only
    replaced once the one-time link has been confirmed
    (`POST /auth/confirm-email-change`), which re-verifies ownership of
    the new address.

    **Path params** — `user_id`: UUID of the user.
    **Body** `application/json`:
    ```json
    { "password": "<current_password>", "new_email": "new@example.com" }
    ```

    **Success** `200` — confirmation message.
    **Errors** — `401`, `403`, `404`, `409`, `422`.
    """
    current_user_id = request.headers.get("X-User-Id", "")
    if not current_user_id or current_user_id != user_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "You can only change the email of your own account."},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Invalid JSON body."},
        )

    password = body.get("password")
    new_email = body.get("new_email")
    if not (isinstance(password, str) and password):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Password confirmation is required."},
        )
    if not (isinstance(new_email, str) and new_email):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "new_email is required."},
        )
    if not await _confirm_password(user_id, password):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "Invalid password. Email not changed."},
        )

    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/internal/email-change",
            json={"user_id": user_id, "new_email": new_email},
            headers={"X-Internal-Key": settings.internal_api_key} if settings.internal_api_key else {},
            timeout=10.0,
        )
        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from auth service"}
        return JSONResponse(content=content, status_code=response.status_code)
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



