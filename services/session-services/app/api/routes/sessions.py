from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user_id
from app.schemas.session import (
    CreateSessionRequest,
    MessageResponse,
    RevokeAllSessionsRequest,
    RevokeSessionRequest,
    RotateSessionRequest,
    SessionListResponse,
    SessionResponse,
    ValidateSessionRequest,
    ValidateSessionResponse,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])

def get_session_service(db: AsyncSession = Depends(get_db)) -> SessionService:
    return SessionService(db)

# --- Internal routes (called by auth-service) -----------------------------------------------------

@router.post(
    "/create",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Internal] Create session",
    include_in_schema=False,
    operation_id="create",
)
async def create_session(data: CreateSessionRequest, service: SessionService = Depends(get_session_service)):
    """
    Creates a session after login or registration.
    Called by the auth-service with the refresh token hash.
    """
    return await service.create_session(data)

@router.post(
    "/validate",
    response_model=ValidateSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Validate refresh token",
    include_in_schema=False,
    operation_id="validate-refresh-token",
)
async def validate_session(
        data: ValidateSessionRequest,
        service: SessionService = Depends(get_session_service)
):
    """
    Validates a refresh token.
    Called by the auth-service during token refresh.
    """
    return await service.validate_session(data)

@router.post(
    "/revoke",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Revoke session by token",
    include_in_schema=False,
    operation_id="revoke",
)
async def revoke_session(data: RevokeSessionRequest, service: SessionService = Depends(get_session_service)):
    """
    Revokes a session using its refresh token.
    Called by the auth-service upon logout.
    """
    return await service.revoke_session(data)

@router.post(
    "/internal/revoke-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Revoke all sessions by user",
    include_in_schema=False,
    operation_id="revoke-all-internal",
)
async def revoke_all_sessions_internal(
        data: RevokeAllSessionsRequest,
        service: SessionService = Depends(get_session_service)
):
    """
    Revokes all active sessions for a user.
    Called by the auth-service after a password reset.
    """
    return await service.revoke_all_sessions(data.user_id)

@router.post(
    "/rotate",
    response_model=ValidateSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Rotate refresh token",
    include_in_schema=False,
    operation_id="rotate-refresh-token",
)
async def rotate_session(
        data: RotateSessionRequest,
        service: SessionService = Depends(get_session_service)
):
    """
    Refresh token rotation.
    Called by the auth-service during refresh.
    """
    return await service.rotate_session(
        old_refresh_token=data.old_refresh_token,
        new_refresh_token_hash=data.new_refresh_token_hash,
        new_expires_at=data.new_expires_at,
    )

# --- Public routes (via gateway) ------------------------------------------------------------------

@router.get(
    "/",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active sessions",
    operation_id="list",
)
async def list_sessions(
        user_id: str = Depends(get_current_user_id),
        service: SessionService = Depends(get_session_service)
):
    """
    Lists the active sessions of the logged-in user.
    `user_id` is automatically extracted from `X-User-Id`, which is injected by the gateway.
    """
    return await service.list_sessions(user_id)

@router.delete(
    "/revoke-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all sessions",
    operation_id="revoke-all",
)
async def revoke_all_sessions(
        user_id: str = Depends(get_current_user_id),
        service: SessionService = Depends(get_session_service)
):
    """Revokes all sessions of the logged-in user."""
    return await service.revoke_all_sessions(user_id)

@router.delete(
    '/{session_id}',
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke session by ID",
    operation_id='revoke-by-id',
)
async def revoke_session_by_id(
        session_id: str,
        user_id: str = Depends(get_current_user_id),
        service: SessionService = Depends(get_session_service)
):
    """Revokes a specific session of the logged-in user."""
    return await service.revoke_session_by_id(session_id=session_id, user_id=user_id)