import logging

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_internal_key
from app.schemas.auth import (
    AuthResponse,
    ConfirmDeletionRequest,
    ConfirmEmailChangeRequest,
    CreateDeletionRequestRequest,
    DeletionRequestResponse,
    EmailChangeRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    VerifyEmailResponse,
    VerifyPasswordRequest,
    VerifyPasswordResponse,
)
from app.services.auth_service import AuthService

logger = logging.getLogger("auth-service")

router = APIRouter(prefix="/auth", tags=["auth"])

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

def _get_client_ip(request: Request) -> str:
    """Extracts the IP from X-Forwarded-For or directly."""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"

def _get_device_info(request: Request, client_ip: str) -> str:
    """Builds the device info string from the User-Agent + IP."""
    user_agent = request.headers.get("User-Agent", "unknown")
    return f"{user_agent} | {client_ip}"

@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    operation_id="register",
)
async def register(
    request: Request,
    data: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Creates a new user account.

        - Creates the profile in user-service
        - Hashes the password with Argon2id
        - Stores the credential in identyx_auth (auth-service's database)
        - Returns the profile + tokens (real tokens in token-service)

    Password rules: minimum 8 characters, 1 uppercase letter, 1 number, 1 punctuation mark.
    """
    client_ip = _get_client_ip(request)
    device_info = _get_device_info(request, client_ip)
    return await service.register(data, device_info=device_info)

@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    operation_id="login",
)
async def login(
    request: Request,
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Connects an existing user.

        - Verifies credentials with Argon2id
        - Updates the hash if needs_rehash (silently)
        - Returns the profile + tokens (real tokens in token-service)

    Login with brute-force protection + device tracking (User-Agent + IP).
    """
    client_ip = _get_client_ip(request)
    device_info = _get_device_info(request, client_ip)
    return await service.login(
        data,
        device_info=device_info,
        client_ip=client_ip,
    )

@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout",
    operation_id="logout",
)
async def logout(
    request: Request,
    data: LogoutRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Disconnect the user.

    The gateway has already enriched the body with `access_token` extracted from the Authorization header.
    `auth-service` revokes the session AND blacklists the access token.
    """
    access_token = request.headers.get("X-Access-Token", "").strip() or None

    logger.info("logout_received", extra={
        "refresh_token_prefix": data.refresh_token[:20],
        "has_access_token": bool(access_token),
    })

    return await service.logout(
        refresh_token=data.refresh_token,
        access_token=access_token,
    )

@router.post(
    "/refresh",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh token",
    operation_id="refresh-token",
)
async def refresh(
    data: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Exchange a valid refresh token for a new access token
    and a new refresh token (rotation).
    """
    return await service.refresh(data.refresh_token)

@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    operation_id="verify-email",
)
async def verify_email(
        token: str = Query(..., description="HMAC verification token from email link"),
        service: AuthService = Depends(get_auth_service),
):
    """
    Verifies the user's email address.
    The token is extracted from the link in the verification email.
    Format: GET /auth/verify-email?token=xxx
    """
    return await service.verify_email(raw_token=token)

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with one-time token",
    operation_id="reset-password",
)
async def reset_password(
        data: ResetPasswordRequest,
        service: AuthService = Depends(get_auth_service),
):
    """
    Sets a new password using a one-time reset token.

    The token comes from the security email link
    (sent after a suspicious login). It is HMAC-signed,
    single-use and expires after 1 hour.
    All sessions are revoked after the change.
    """
    return await service.reset_password(
        raw_token=data.token,
        new_password=data.new_password,
    )

@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend the email verification link",
    operation_id="resend-verification",
)
async def resend_verification(
        data: ResendVerificationRequest,
        service: AuthService = Depends(get_auth_service),
):
    """
    Re-sends the verification email if the user never received it.

    - The email is not disclosed (generic response)
    - If the account is already verified, nothing is resent
    - A fresh HMAC token is generated and stored (single-use, 24h)
    """
    return await service.resend_verification(data.email)

@router.post(
    "/internal/verify-password",
    response_model=VerifyPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Confirm the account password",
    operation_id="verify-password",
    include_in_schema=False,
)
async def verify_password(
        data: VerifyPasswordRequest,
        service: AuthService = Depends(get_auth_service),
        _: None = Depends(require_internal_key),
):
    """
    Confirms a user's password for destructive operations.

    Called by the gateway before DELETE /users/{user_id} and
    DELETE /users/{user_id}/avatar. The password is never stored
    or transmitted beyond this service (Argon2id verification only).
    """
    return await service.verify_password(data.user_id, data.password)

@router.post(
    "/internal/deletion-request",
    response_model=DeletionRequestResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Start a GDPR account deletion",
    operation_id="create-deletion-request",
    include_in_schema=False,
)
async def create_deletion_request(
        data: CreateDeletionRequestRequest,
        service: AuthService = Depends(get_auth_service),
        _: None = Depends(require_internal_key),
):
    """
    Starts a GDPR account deletion for a user.

    Called by the gateway after the password has been confirmed.
    Sends a confirmation email containing a one-time deletion link.
    """
    return await service.create_deletion_request(data.user_id)

@router.post(
    "/confirm-deletion",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm account deletion (GDPR)",
    operation_id="confirm-deletion",
)
async def confirm_deletion(
        data: ConfirmDeletionRequest,
        service: AuthService = Depends(get_auth_service),
):
    """
    Permanently deletes an account using the one-time email token.

    The token comes from the deletion confirmation email link.
    It is HMAC-signed, single-use and expires after 24h.
    This operation is irreversible.
    """
    return await service.confirm_deletion(data.token)

@router.post(
    "/internal/email-change",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Start an email address change",
    operation_id="request-email-change",
    include_in_schema=False,
)
async def request_email_change(
        data: EmailChangeRequest,
        service: AuthService = Depends(get_auth_service),
        _: None = Depends(require_internal_key),
):
    """
    Starts an email address change for a user.

    Called by the gateway after the password has been confirmed.
    Sends a confirmation email to the NEW address.
    """
    return await service.request_email_change(data.user_id, data.new_email)

@router.post(
    "/confirm-email-change",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm email address change",
    operation_id="confirm-email-change",
)
async def confirm_email_change(
        data: ConfirmEmailChangeRequest,
        service: AuthService = Depends(get_auth_service),
):
    """
    Applies an email change using the one-time token.

    The token comes from the confirmation email sent to the NEW address.
    It is HMAC-signed, single-use and expires after 24h.
    """
    return await service.confirm_email_change(data.token)