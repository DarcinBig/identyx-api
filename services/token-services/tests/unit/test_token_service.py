"""Unit tests for TokenService."""
import pytest
from unittest.mock import patch

class TestTokenGeneration:

    @pytest.mark.asyncio
    async def test_generate_returns_access_and_refresh(self, fake_redis):
        from app.services.token_service import TokenService
        from app.schemas.token import GenerateTokenRequest

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
        from app.services.token_service import TokenService
        from app.schemas.token import GenerateTokenRequest

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            result = await service.generate(GenerateTokenRequest(user_id="uuid-123"))

        parts = result.access_token.split(".")
        assert len(parts) == 3

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, fake_redis):
        """A freshly generated token must be valid."""
        from app.services.token_service import TokenService
        from app.schemas.token import GenerateTokenRequest, VerifyTokenRequest

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            generated = await service.generate(GenerateTokenRequest(user_id="uuid-123"))
            result = await service.verify(VerifyTokenRequest(access_token=generated.access_token))

        assert result.valid is True
        assert result.user_id == "uuid-123"

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, fake_redis):
        """A malformed token must return valid=False."""
        from app.services.token_service import TokenService
        from app.schemas.token import VerifyTokenRequest

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            result = await service.verify(VerifyTokenRequest(access_token="invalid.token.here"))

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_revoke_blacklists_token(self, fake_redis):
        """A revoked token must return valid=False."""
        from app.services.token_service import TokenService
        from app.schemas.token import GenerateTokenRequest, VerifyTokenRequest, RevokeTokenRequest

        with patch("app.cache.redis.get_redis", return_value=fake_redis):
            service = TokenService()
            generated = await service.generate(GenerateTokenRequest(user_id="uuid-123"))

            # Revoke
            await service.revoke(RevokeTokenRequest(access_token=generated.access_token))

            # Verify — must be invalid
            result = await service.verify(VerifyTokenRequest(access_token=generated.access_token))

        assert result.valid is False