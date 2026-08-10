"""Unit tests for TokenService."""
from unittest.mock import patch

import pytest


class TestTokenGeneration:

    @pytest.mark.asyncio
    async def test_generate_returns_access_and_refresh(self, fake_redis):
        from app.schemas.token import GenerateTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            request = GenerateTokenRequest(user_id="uuid-123")
            result = await service.generate(request)

        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.refresh_token_hash is not None
        assert result.expires_in > 0

    @pytest.mark.asyncio
    async def test_generate_access_token_is_jwt(self, fake_redis):
        """The access token must be a valid JWT (3 parts separated by .)."""
        from app.schemas.token import GenerateTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            result = await service.generate(GenerateTokenRequest(user_id="uuid-123"))

        parts = result.access_token.split(".")
        assert len(parts) == 3

    @pytest.mark.asyncio
    async def test_generate_access_token_has_iss_aud_claims(self, fake_redis):
        """The access token must carry iss/aud claims and validate against them."""
        from jose import jwt as jose_jwt

        from app.core.config import get_settings
        from app.schemas.token import GenerateTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            result = await service.generate(GenerateTokenRequest(user_id="uuid-123"))

        settings = get_settings()
        payload = jose_jwt.decode(
            result.access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        assert payload["iss"] == settings.jwt_issuer
        assert payload["aud"] == settings.jwt_audience
        assert payload["sub"] == "uuid-123"

    @pytest.mark.asyncio
    async def test_verify_rejects_wrong_audience(self, fake_redis):
        """A token signed for a different audience must be rejected."""
        from jose import jwt as jose_jwt

        from app.core.config import get_settings
        from app.schemas.token import GenerateTokenRequest, VerifyTokenRequest
        from app.services.token_service import TokenService

        settings = get_settings()
        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            await service.generate(GenerateTokenRequest(user_id="uuid-123"))
            wrong_aud = jose_jwt.encode(
                {"sub": "uuid-123", "aud": "other-app"},
                settings.jwt_secret_key,
                algorithm=settings.jwt_algorithm,
            )
            result = await service.verify(VerifyTokenRequest(access_token=wrong_aud))

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, fake_redis):
        """A freshly generated token must be valid."""
        from app.schemas.token import GenerateTokenRequest, VerifyTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            generated = await service.generate(GenerateTokenRequest(user_id="uuid-123"))
            result = await service.verify(VerifyTokenRequest(access_token=generated.access_token))

        assert result.valid is True
        assert result.user_id == "uuid-123"

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, fake_redis):
        """A malformed token must return valid=False."""
        from app.schemas.token import VerifyTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            result = await service.verify(VerifyTokenRequest(access_token="invalid.token.here"))

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_revoke_blacklists_token(self, fake_redis):
        """A revoked token must return valid=False."""
        from app.schemas.token import GenerateTokenRequest, RevokeTokenRequest, VerifyTokenRequest
        from app.services.token_service import TokenService

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            generated = await service.generate(GenerateTokenRequest(user_id="uuid-123"))

            # Revoke
            await service.revoke(RevokeTokenRequest(access_token=generated.access_token))

            # Verify — must be invalid
            result = await service.verify(VerifyTokenRequest(access_token=generated.access_token))

        assert result.valid is False