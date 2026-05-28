from fastapi import APIRouter, status

from app.schemas.token import (
    GenerateTokenRequest,
    VerifyTokenRequest,
    RevokeTokenRequest,
    TokenPairResponse,
    VerifyTokenResponse,
    RevokeTokenResponse,
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
)
async def generate_tokens(data: GenerateTokenRequest):
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
    """
    return await _service.verify(token)

@router.post(
    "/revoke",
    response_model=RevokeTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke access token",
    operation_id="revoke",
)
async def revoke_token(token: RevokeTokenRequest):
    """
    Revokes an access token (Redis blacklist + TTL).
    Called by the auth-service during logout.
    """
    return await _service.revoke(token)