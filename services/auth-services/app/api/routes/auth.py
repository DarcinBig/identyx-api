from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    VerifyEmailResponse,
)
from app.services.auth_service import AuthService

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

    print(f"[route/logout] refresh_token: {data.refresh_token[:20]}...")
    print(f"[route/logout] access_token header: {access_token[:30] if access_token else 'None'}")

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