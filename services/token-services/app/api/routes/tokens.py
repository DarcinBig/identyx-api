import logging
import time

from fastapi import APIRouter, HTTPException, status
from jose import jwt

from app.schemas.token import (
    GenerateTokenRequest,
    RevokeTokenRequest,
    RevokeTokenResponse,
    TokenPairResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from app.services.token_service import TokenService

logger = logging.getLogger("uvicorn.error")

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
    try:
        from app.core.config import get_settings
        settings = get_settings()
        payload = jwt.decode(token.access_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            raise HTTPException(status_code=400, detail="Invalid token payload")
        ttl = exp - int(time.time())
        logger.info(f"[revoke] jti={jti}, ttl={ttl}")
    except Exception as exc:
        logger.warning(f"[revoke] Could not decode token: {exc}")
    return await _service.revoke(token)