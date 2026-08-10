"""Unit tests for the GDPR account deletion and email change flows."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


class TestCreateDeletionRequest:

    @pytest.mark.asyncio
    async def test_create_deletion_request_success(self):
        """A deletion request must store a token and publish the event."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._get_user_by_id = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "user@example.com",
            "username": "user",
        })
        service._store_deletion_token = AsyncMock()
        service._publish_deletion_requested = AsyncMock()

        with patch(
            "app.services.auth_service.generate_verification_token",
            return_value="uuid-123.delete_account.1234.sig",
        ):
            result = await service.create_deletion_request("uuid-123")

        assert "email" in result.message.lower()
        service._store_deletion_token.assert_awaited_once_with(
            user_id="uuid-123",
            raw_token="uuid-123.delete_account.1234.sig",
        )
        service._publish_deletion_requested.assert_awaited_once_with(
            user_id="uuid-123",
            email="user@example.com",
            username="user",
            deletion_token="uuid-123.delete_account.1234.sig",
        )

    @pytest.mark.asyncio
    async def test_create_deletion_request_unknown_user(self):
        """An unknown user must return 404."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._get_user_by_id = AsyncMock(side_effect=HTTPException(
            status_code=404, detail="User not found"
        ))

        with pytest.raises(HTTPException) as exc_info:
            await service.create_deletion_request("uuid-404")

        assert exc_info.value.status_code == 404


class TestConfirmDeletion:

    @pytest.mark.asyncio
    async def test_confirm_deletion_success(self):
        """A valid token must delete the profile, the credential and revoke sessions."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service.repo = AsyncMock()
        service.repo.delete_by_user_id = AsyncMock()
        service._check_deletion_token = AsyncMock(
            return_value={"valid": True, "detail": ""}
        )
        service._confirm_deletion = AsyncMock(
            return_value={"email": "user@example.com", "deleted": True}
        )
        service._revoke_all_sessions = AsyncMock()
        service._publish_user_deleted = AsyncMock()

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(True, "uuid-123"),
        ):
            result = await service.confirm_deletion(
                raw_token="uuid-123.delete_account.1234.sig",
            )

        assert result.message == "Account permanently deleted."
        service.repo.delete_by_user_id.assert_awaited_once_with("uuid-123")
        service._revoke_all_sessions.assert_awaited_once_with("uuid-123")
        service._publish_user_deleted.assert_awaited_once_with(
            user_id="uuid-123",
            email="user@example.com",
        )

    @pytest.mark.asyncio
    async def test_confirm_deletion_invalid_signature(self):
        """A forged signature must be rejected with a generic 400."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(False, None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.confirm_deletion(raw_token="forged.token.here")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid or expired deletion token."

    @pytest.mark.asyncio
    async def test_confirm_deletion_db_token_invalid(self):
        """A valid signature but an expired/used DB token must be rejected."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._check_deletion_token = AsyncMock(
            return_value={"valid": False, "detail": "Deletion token expired."}
        )

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(True, "uuid-123"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.confirm_deletion(
                    raw_token="uuid-123.delete_account.1234.sig",
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid or expired deletion token."


class TestEmailChange:

    @pytest.mark.asyncio
    async def test_request_email_change_success(self):
        """A valid request must store the token + pending email and publish."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._get_user_by_id = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "old@example.com",
            "username": "user",
        })
        service._get_user_by_email = AsyncMock(
            side_effect=HTTPException(status_code=401, detail="Invalid email or password")
        )
        service._store_email_change_token = AsyncMock()
        service._publish_email_change_requested = AsyncMock()

        with patch(
            "app.services.auth_service.generate_verification_token",
            return_value="uuid-123.email_change.1234.sig",
        ):
            result = await service.request_email_change(
                user_id="uuid-123",
                new_email="new@example.com",
            )

        assert "email" in result.message.lower()
        service._store_email_change_token.assert_awaited_once_with(
            user_id="uuid-123",
            raw_token="uuid-123.email_change.1234.sig",
            pending_email="new@example.com",
        )
        service._publish_email_change_requested.assert_awaited_once_with(
            user_id="uuid-123",
            email="new@example.com",
            username="user",
            email_change_token="uuid-123.email_change.1234.sig",
        )

    @pytest.mark.asyncio
    async def test_request_email_change_same_email_rejected(self):
        """Using the current email must return 400."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._get_user_by_id = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "old@example.com",
            "username": "user",
        })

        with pytest.raises(HTTPException) as exc_info:
            await service.request_email_change(
                user_id="uuid-123",
                new_email="old@example.com",
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_request_email_change_already_registered(self):
        """An email already registered by another account must return 409."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._get_user_by_id = AsyncMock(return_value={
            "id": "uuid-123",
            "email": "old@example.com",
            "username": "user",
        })
        service._get_user_by_email = AsyncMock(return_value={
            "id": "uuid-999",
            "email": "taken@example.com",
        })

        with pytest.raises(HTTPException) as exc_info:
            await service.request_email_change(
                user_id="uuid-123",
                new_email="taken@example.com",
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_confirm_email_change_success(self):
        """A valid token must apply the new email."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)
        service._check_email_change_token = AsyncMock(
            return_value={"valid": True, "detail": ""}
        )
        service._confirm_email_change = AsyncMock(
            return_value={"email": "new@example.com", "confirmed": True}
        )

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(True, "uuid-123"),
        ):
            result = await service.confirm_email_change(
                raw_token="uuid-123.email_change.1234.sig",
            )

        assert result.message == "Email address updated successfully."
        service._confirm_email_change.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirm_email_change_invalid_token(self):
        """An invalid signature or DB token must be rejected with a generic 400."""
        mock_db = AsyncMock()
        from app.services.auth_service import AuthService

        service = AuthService(mock_db)

        with patch(
            "app.services.auth_service.verify_verification_token",
            return_value=(False, None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await service.confirm_email_change(raw_token="forged.token.here")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid or expired email change token."
