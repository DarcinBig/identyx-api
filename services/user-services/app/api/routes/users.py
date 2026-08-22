from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user_id, require_internal_key
from app.schemas.user import (
    AvatarResponse,
    CheckDeletionRequestTokenRequest,
    CheckDeletionRequestTokenResponse,
    CheckEmailChangeTokenRequest,
    CheckEmailChangeTokenResponse,
    CheckPasswordResetTokenRequest,
    CheckPasswordResetTokenResponse,
    CheckVerificationTokenRequest,
    CheckVerificationTokenResponse,
    ConfirmDeletionRequest,
    ConfirmDeletionResponse,
    ConfirmEmailChangeRequest,
    ConfirmEmailChangeResponse,
    ConfirmPasswordResetRequest,
    ConfirmPasswordResetResponse,
    ConfirmVerificationRequest,
    ConfirmVerificationResponse,
    StoreDeletionRequestTokenRequest,
    StoreEmailChangeTokenRequest,
    StorePasswordResetTokenRequest,
    StoreVerificationTokenRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])

def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)

def _ensure_owner(user_id: str, current_user_id: str) -> None:
    """Users may only read/write their own profile."""
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own account.",
        )

# --- CRUD --------------------------------------------------------------

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Create a new user",
    operation_id="create",
    include_in_schema=False,
)
async def create_user(
        data: UserCreate,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
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
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    _ensure_owner(user_id, current_user_id)
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
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    _ensure_owner(user_id, current_user_id)
    return await service.update_user(user_id, data)

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete user",
    operation_id="delete"
)
async def delete_user(
        user_id: str,
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    _ensure_owner(user_id, current_user_id)
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
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    """
    Upload a profile picture from the user's device.

    - Accepted formats: JPEG, PNG, WebP
    - Maximum size: 5 MB
    - The old photo is automatically replaced
    - Returns the public raw URL of the new photo
    """
    _ensure_owner(user_id, current_user_id)
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
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    """
    Returns the raw public URL of the avatar.
    Always a valid URL — never None.
    """
    _ensure_owner(user_id, current_user_id)
    return await service.delete_avatar(user_id=user_id)

@router.get(
    "/{user_id}/avatar",
    response_model=AvatarResponse,
    summary="Get avatar URL",
    operation_id="avatar-url"
)
async def get_avatar(
        user_id: str,
        current_user_id: str = Depends(get_current_user_id),
        service: UserService = Depends(get_user_service)
):
    """
    Returns the raw public URL of the avatar.
    Always a valid URL — never None.
    """
    _ensure_owner(user_id, current_user_id)
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
        tenant_id: str = Query(..., description="Tenant ID (required)"),
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Used by the auth-service during login.
    GET /users/internal/by-email?email=user@example.com&tenant_id=xxx
    """
    return await service.get_user_by_email(email, tenant_id=tenant_id)

@router.get(
    "/internal/by-id",
    response_model=UserResponse,
    summary="[Internal] Get user by ID",
    include_in_schema=False,
    operation_id="get-user-by-id",
)
async def get_user_by_id_internal(
        user_id: str,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Used by the auth-service during refresh and logout.
    GET /users/internal/by-id?user_id=...
    """
    return await service.get_user_by_id(user_id)

# --- Internal endpoints — email verification (auth-service) ------------------------------

@router.post(
    "/internal/verification-token",
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Store verification token",
    include_in_schema=False,
    operation_id="store-verification-token",
)
async def store_verification_token(
        data: StoreVerificationTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Stores an email verification token.
    Called by auth-service after register.
    """
    await service.store_verification_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return {"message": "Verification token stored."}

@router.post(
    "/internal/verify-token",
    response_model=CheckVerificationTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Check verification token",
    include_in_schema=False,
    operation_id="check-verification-token",
)
async def check_verification_token(
        data: CheckVerificationTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Checks the token in DB (expiration + is_used).
    Called by auth-service during email verification.
    """
    result = await service.check_verification_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return CheckVerificationTokenResponse(**result)

@router.post(
    "/internal/confirm-verification",
    response_model=ConfirmVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Confirm email verification",
    include_in_schema=False,
    operation_id="confirm-verification",
)
async def confirm_verification(
        data: ConfirmVerificationRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Marks the token as used AND the email as verified.
    Called by auth-service after successful HMAC verification.
    """
    result = await service.confirm_email_verification(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return ConfirmVerificationResponse(**result)

# --- Internal endpoints — password reset (auth-service) ------------------------------

@router.post(
    "/internal/password-reset-token",
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Store password reset token",
    include_in_schema=False,
    operation_id="store-password-reset-token",
)
async def store_password_reset_token(
        data: StorePasswordResetTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Stores a password reset token.
    Called by auth-service when a suspicious login is detected.
    """
    await service.store_password_reset_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return {"message": "Password reset token stored."}

@router.post(
    "/internal/check-password-reset-token",
    response_model=CheckPasswordResetTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Check password reset token",
    include_in_schema=False,
    operation_id="check-password-reset-token",
)
async def check_password_reset_token(
        data: CheckPasswordResetTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Checks the password reset token in DB (expiration + is_used).
    Called by auth-service during password reset.
    """
    result = await service.check_password_reset_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return CheckPasswordResetTokenResponse(**result)

@router.post(
    "/internal/confirm-password-reset",
    response_model=ConfirmPasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Confirm password reset",
    include_in_schema=False,
    operation_id="confirm-password-reset",
)
async def confirm_password_reset(
        data: ConfirmPasswordResetRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Marks the password reset token as used.
    Called by auth-service after the password has been changed.
    """
    result = await service.confirm_password_reset(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return ConfirmPasswordResetResponse(**result)

# --- Internal endpoints — account deletion (GDPR, auth-service) -----------------------------

@router.post(
    "/internal/deletion-request-token",
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Store deletion confirmation token",
    include_in_schema=False,
    operation_id="store-deletion-request-token",
)
async def store_deletion_request_token(
        data: StoreDeletionRequestTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Stores an account deletion confirmation token.
    Called by auth-service when the owner requests a GDPR deletion.
    """
    await service.store_deletion_request_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return {"message": "Deletion request token stored."}

@router.post(
    "/internal/check-deletion-token",
    response_model=CheckDeletionRequestTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Check deletion confirmation token",
    include_in_schema=False,
    operation_id="check-deletion-token",
)
async def check_deletion_request_token(
        data: CheckDeletionRequestTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Checks the deletion token in DB (expiration + is_used).
    Called by auth-service during account deletion confirmation.
    """
    result = await service.check_deletion_request_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return CheckDeletionRequestTokenResponse(**result)

@router.post(
    "/internal/confirm-deletion",
    response_model=ConfirmDeletionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Confirm account deletion",
    include_in_schema=False,
    operation_id="confirm-deletion",
)
async def confirm_deletion(
        data: ConfirmDeletionRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Marks the deletion token as used AND permanently deletes the user.
    Atomic call. Called by auth-service after successful HMAC verification.
    """
    result = await service.confirm_deletion(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return ConfirmDeletionResponse(**result)

# --- Internal endpoints — email change (auth-service) ----------------------------------------

@router.post(
    "/internal/email-change-token",
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Store email change token",
    include_in_schema=False,
    operation_id="store-email-change-token",
)
async def store_email_change_token(
        data: StoreEmailChangeTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Stores an email change request.
    Called by auth-service when the owner asks to change their email.
    """
    await service.store_email_change_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
        pending_email=data.pending_email,
    )
    return {"message": "Email change token stored."}

@router.post(
    "/internal/check-email-change-token",
    response_model=CheckEmailChangeTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Check email change token",
    include_in_schema=False,
    operation_id="check-email-change-token",
)
async def check_email_change_token(
        data: CheckEmailChangeTokenRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Checks the email change token in DB (expiration + is_used).
    Called by auth-service during email change confirmation.
    """
    result = await service.check_email_change_token(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return CheckEmailChangeTokenResponse(**result)

@router.post(
    "/internal/confirm-email-change",
    response_model=ConfirmEmailChangeResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Confirm email change",
    include_in_schema=False,
    operation_id="confirm-email-change",
)
async def confirm_email_change(
        data: ConfirmEmailChangeRequest,
        service: UserService = Depends(get_user_service),
        _: None = Depends(require_internal_key),
):
    """
    Marks the email change token as used AND applies the pending email.
    Atomic call. Called by auth-service after successful HMAC verification.
    """
    result = await service.confirm_email_change(
        user_id=data.user_id,
        raw_token=data.raw_token,
    )
    return ConfirmEmailChangeResponse(**result)
