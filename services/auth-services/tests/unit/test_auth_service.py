"""Unit tests for AuthService using mocks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


class TestAuthServiceResetPassword:

    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """A valid one-time token must update the password and revoke all sessions."""
        mock_db = AsyncMock()

        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        service.repo = AsyncMock()
        service.repo.update_password = AsyncMock(return_value=True)

        service._check_password_reset_token = AsyncMock(
            return_value={"valid": True, "detail": ""}
        )
        service._confirm_password_reset = AsyncMock(
            return_value={"confirmed": True}
        )
        service._revoke_all_sessions = AsyncMock()

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(True, "uuid-123"),
        ):
            result = await service.reset_password(
                raw_token="uuid-123.1234.signature",
                new_password="NewPassword@1",
            )

        assert result.message == "Password updated successfully."
        service.repo.update_password.assert_awaited_once()
        service._confirm_password_reset.assert_awaited_once()
        service._revoke_all_sessions.assert_awaited_once_with("uuid-123")

    @pytest.mark.asyncio
    async def test_reset_password_invalid_signature(self):
        """An invalid HMAC signature must raise a generic 400."""
        mock_db = AsyncMock()

        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(False, None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.reset_password(
                    raw_token="forged.token.here",
                    new_password="NewPassword@1",
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid or expired reset token."

    @pytest.mark.asyncio
    async def test_reset_password_db_token_invalid(self):
        """A valid signature but an expired/used DB token must be rejected."""
        mock_db = AsyncMock()

        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(True, "uuid-123"),
        ):
            service._check_password_reset_token = AsyncMock(
                return_value={"valid": False, "detail": "Password reset token expired."}
            )

            with pytest.raises(HTTPException) as exc_info:
                await service.reset_password(
                    raw_token="uuid-123.1234.signature",
                    new_password="NewPassword@1",
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid or expired reset token."


class TestAuthServiceRegister:

    @pytest.mark.asyncio
    async def test_register_calls_create_user_profile(self):
        """Register must call user-service to create the profile."""
        mock_db = AsyncMock()

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "uuid-123",
                "email": "test@example.com",
                "username": "testuser",
                "is_verified": False,
                "avatar_url": "https://example.com/avatar.png",
                "avatar_provider": "default",
            }
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            from app.schemas.auth import RegisterRequest
            from app.services.auth_service import AuthService

            service = AuthService(mock_db)

            # Mock internal methods
            service._generate_tokens = AsyncMock(return_value={
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "refresh_token_hash": "hash",
                "expires_in": 1799,
            })
            service._create_session = AsyncMock()
            service._publish_user_registered = AsyncMock()
            service.repo = AsyncMock()
            service.repo.create = AsyncMock()

            data = RegisterRequest(
                email="test@example.com",
                username="testuser",
                password="TestPassword@1",
            )

            result = await service.register(data)
            assert result.user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_register_raises_on_duplicate_email(self):
        """Register must raise an HTTPException 409 if the email already exists."""
        mock_db = AsyncMock()

        with patch("app.services.auth_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 409
            mock_response.json.return_value = {"detail": "Email already registered"}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            from app.schemas.auth import RegisterRequest
            from app.services.auth_service import AuthService

            service = AuthService(mock_db)

            data = RegisterRequest(
                email="test@example.com",
                username="testuser",
                password="TestPassword@1",
            )

            with pytest.raises(HTTPException) as exc_info:
                await service.register(data)

            assert exc_info.value.status_code == 409

class TestAuthServiceLogin:

    @pytest.mark.asyncio
    async def test_login_raises_on_wrong_password(self):
        """Login must raise an HTTPException 401 if the password is incorrect."""
        mock_db = AsyncMock()

        from app.schemas.auth import LoginRequest
        from app.security.hashing import hash_password
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        # Mock the user profile
        service._get_user_by_email = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "test@example.com",
            "username": "testuser",
            "is_verified": False,
            "avatar_url": None,
            "avatar_provider": "default",
        })

        # Mock the credential with a hash of the incorrect password.
        mock_credential = MagicMock()
        mock_credential.hashed_password = hash_password("CorrectPassword@1")
        service.repo = AsyncMock()
        service.repo.get_by_user_id = AsyncMock(return_value=mock_credential)

        data = LoginRequest(
            email="test@example.com",
            password="WrongPassword@1",
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.login(data, client_ip="127.0.0.1")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_success_returns_tokens(self):
        """A successful login must return an access_token and a refresh_token."""
        mock_db = AsyncMock()

        from app.schemas.auth import LoginRequest
        from app.security.hashing import hash_password
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        correct_password = "CorrectPass@1"

        service._get_user_by_email = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "test@example.com",
            "username": "testuser",
            "is_verified": False,
            "avatar_url": "https://example.com/avatar.png",
            "avatar_provider": "default",
        })

        mock_credential = MagicMock()
        mock_credential.hashed_password = hash_password(correct_password)
        service.repo = AsyncMock()
        service.repo.get_by_user_id = AsyncMock(return_value=mock_credential)

        service._generate_tokens = AsyncMock(return_value={
            "access_token": "access_jwt",
            "refresh_token": "refresh_opaque",
            "refresh_token_hash": "hash123",
            "expires_in": 1799,
        })
        service._create_session = AsyncMock()
        service._publish_auth_login = AsyncMock()

        with patch("app.security.brute_force.check_brute_force", new=AsyncMock()), \
                patch("app.security.brute_force.reset_brute_force", new=AsyncMock()):
            data = LoginRequest(
                email="test@example.com",
                password=correct_password,
            )

            result = await service.login(data, client_ip="127.0.0.1")

        assert result.access_token == "access_jwt"
        assert result.refresh_token == "refresh_opaque"
        assert result.user.email == "test@example.com"