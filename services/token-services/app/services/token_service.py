import logging
from datetime import UTC, datetime

from fastapi import HTTPException

from app.cache.redis import blacklist_token, is_blacklisted
from app.core.config import get_settings
from app.schemas.token import (
    GenerateTokenRequest,
    RevokeTokenRequest,
    RevokeTokenResponse,
    TokenPairResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from app.security.jwt import decode_access_token, generate_access_token, generate_refresh_token

settings = get_settings()
logger = logging.getLogger("uvicorn.error")

class TokenService:
    async def generate(self, data: GenerateTokenRequest) -> TokenPairResponse:
        """
        Generates an access token and a refresh token pair.

        Flow:
            1. Generate the HS256-signed JWT access token
            2. Calculate `expires_in` in seconds
            3. Generate the opaque refresh token and its SHA-256 hash
            4. Return everything — the hash is for the session service (sessions-service)
        """
        access_token, jti, expires_at = generate_access_token(
            user_id=data.user_id,
        )

        now = datetime.now(UTC)
        expires_in = int((expires_at - now).total_seconds())

        raw_refresh, refresh_hash = generate_refresh_token()

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            refresh_token_hash=refresh_hash,
            token_type="Bearer",
            expires_in=expires_in,
        )

    async def verify(self, data: VerifyTokenRequest) -> VerifyTokenResponse:
        """
        Validates an access token.

        Checks in this order:
            1. Signature and expiration (python-jose)
            2. Type = "access"
            3. Presence of the JTI on the Redis blacklist

        Returns valid=True/False without raising an exception —
        Callers decide what to do with the result.
        """
        try:
            payload = decode_access_token(data.access_token)
        except HTTPException:
            return VerifyTokenResponse(valid=False)

        jti = payload.get("jti")
        user_id = payload.get("sub")

        if not jti or not user_id:
            return VerifyTokenResponse(valid=False)

        if await is_blacklisted(jti):
            return VerifyTokenResponse(valid=False)

        return VerifyTokenResponse(
            valid=True,
            user_id=user_id,
            jti=jti,
        )

    async def revoke(self, data: RevokeTokenRequest) -> RevokeTokenResponse:
        """
        Revokes an access token by blacklisting its JTI in Redis.

        Redis TTL = Remaining Life of the Token.
        The key automatically disappears after its natural expiration.

        If the token has already expired or is invalid,
        the return is success — it is, in fact, already invalid.
        """
        # try:
        #     payload = decode_access_token(data.access_token)
        # except HTTPException:
        #     return RevokeTokenResponse(
        #         message="Token already invalid or expired.",
        #     )
        #
        # jti = payload.get("jti")
        # exp = payload.get("exp")
        #
        # if jti and exp:
        #     now = datetime.now(timezone.utc)
        #     exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        #     ttl = max(0, int((exp_dt - now).total_seconds()))
        #
        #     if ttl > 0:
        #         await blacklist_token(jti=jti, ttl_seconds=ttl)
        # return RevokeTokenResponse(
        #     message="Token revoked successfully.",
        # )
        try:
            payload = decode_access_token(data.access_token)
        except HTTPException:
            logger.warning("[revoke] Invalid token received")
            return RevokeTokenResponse(
                message="Token already invalid or expired.",
            )

        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            now = datetime.now(UTC)
            exp_dt = datetime.fromtimestamp(exp, tz=UTC)
            ttl = max(0, int((exp_dt - now).total_seconds()))
            logger.info(f"[revoke] jti={jti}, ttl={ttl} seconds")
            if ttl > 0:
                await blacklist_token(jti=jti, ttl_seconds=ttl)
                logger.info(f"[revoke] Token blacklisted with TTL {ttl}s")
            else:
                logger.info("[revoke] Token already expired, not blacklisted")
        return RevokeTokenResponse(
            message="Token revoked successfully.",
        )