from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user_id
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    AvatarResponse,
    UserListResponse
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

# --- CRUD --------------------------------------------------------------

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    operation_id="create",
)
async def create_user(
        data: UserCreate,
        service: UserService = Depends(get_user_service)
):
    return await service.create_user(data)

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    operation_id="me",
)
async def get_me(
        user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    """
    Returns the profile of the logged-in user.
    `user_id` is automatically extracted from the `X-User-Id` header
    injected by the gateway after JWT validation.
    """
    return await service.get_user_by_id(user_id)

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID",
    operation_id="user-id"
)
async def get_user(
        user_id: str,
        service: UserService = Depends(get_user_service)
):
    return await service.get_user_by_id(user_id)

@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user",
    operation_id="update"
)
async def update_user(
        user_id: str,
        data: UserUpdate,
        service: UserService = Depends(get_user_service)
):
    return await service.update_user(user_id, data)

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete user",
    operation_id="delete"
)
async def delete_user(
        user_id: str,
        service: UserService = Depends(get_user_service)
):
    return await service.delete_user(user_id)

# --- Avatar ---------------------------------------------------------------------

@router.post(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload user avatar",
    operation_id="upload-avatar"
)
async def upload_avatar(
        user_id: str,
        file: UploadFile = File(..., description="Image file (jpeg, jpg, png, webp) — max 5 MB"),
        service: UserService = Depends(get_user_service)
):
    """
    Upload a profile picture from the user's device.

    - Accepted formats: JPEG, PNG, WebP
    - Maximum size: 5 MB
    - The old photo is automatically replaced
    - Returns the public raw URL of the new photo
    """
    return await service.upload_avatar(user_id=user_id, file=file)

@router.delete(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset avatar to default",
    operation_id="reset-avatar"
)
async def delete_avatar(
        user_id: str,
        service: UserService = Depends(get_user_service)
):
    """
    Returns the raw public URL of the avatar.
    Always a valid URL — never None.
    """
    return await service.delete_avatar(user_id=user_id)

@router.get(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    summary="Get avatar URL",
    operation_id="avatar-url"
)
async def get_avatar(
        user_id: str,
        service: UserService = Depends(get_user_service)
):
    """
    Returns the raw public URL of the avatar.
    Always a valid URL — never None.
    """
    return await service.get_avatar_url(user_id=user_id)

# --- Internal endpoints (auth-service) ----------------------------------------

@router.get(
    "/internal/by-email",
    response_model=UserResponse,
    summary="[Internal] Get user by email",
    include_in_schema=False,
    operation_id="get-user-by-email"
)
async def get_user_by_email(
        email: str,
        service: UserService = Depends(get_user_service)
):
    """
    Used by the auth-service during login.
    GET /users/internal/by-email?email=user@example.com
    """
    return await service.get_user_by_email(email)
