from fastapi import APIRouter, Depends, status

from app.dependencies import require_internal_key
from app.schemas.token import (
    GenerateTokenRequest,
    RevokeTokenRequest,
    RevokeTokenResponse,
    TokenPairResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from app.services.token_service import TokenService

router = APIRouter(prefix="/tokens", tags=["tokens"])

# No DB — stateless shared instance
_service = TokenService()

@router.post(
    "/generate",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate token pair",
    operation_id="generate",
    include_in_schema=False,
)
async def generate_tokens(data: GenerateTokenRequest, _: None = Depends(require_internal_key)):
    """
    Generates a JWT access token and an opaque refresh token.
    Called by the auth-service after successful login or registration.
    """
    return await _service.generate(data)

@router.post(
    "/verify",
    response_model=VerifyTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify access token",
    operation_id="verify",
)
async def verify_token(token: VerifyTokenRequest):
    """
    Validates an access token — signature, expiration, blacklist.
    Returns valid=True/False without exception.
    Called by the gateway for every authenticated request.
    """
    return await _service.verify(token)

@router.post(
    "/revoke",
    response_model=RevokeTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke access token",
    operation_id="revoke",
    include_in_schema=False,
)
async def revoke_token(token: RevokeTokenRequest, _: None = Depends(require_internal_key)):
    """
    Revokes an access token (Redis blacklist + TTL).
    Called by the auth-service during logout.
    The decode + blacklist logic lives in TokenService.
    """
    return await _service.revoke(token)