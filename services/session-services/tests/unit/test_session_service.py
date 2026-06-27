"""Unit tests for SessionService."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

class TestSessionService:
    @pytest.mark.asyncio
    async def test_validate_session_returns_false_for_unknown_token(self):
        """Validating an unknown token must return valid=False."""
        mock_db = AsyncMock()

        from app.services.session_service import SessionService
        from app.schemas.session import ValidateSessionRequest

        service = SessionService(mock_db)
        service.repo = AsyncMock()
        service.repo.get_by_token_hash = AsyncMock(return_value=None)

        result = await service.validate_session(
            ValidateSessionRequest(refresh_token="unknown_token")
        )

        assert result.valid is False
        assert result.user_id is None

    @pytest.mark.asyncio
    async def test_validate_session_returns_false_for_revoked(self):
        """Validating a revoked session must return valid=False."""
        mock_db = AsyncMock()

        from app.services.session_service import SessionService
        from app.schemas.session import ValidateSessionRequest

        service = SessionService(mock_db)

        mock_session = MagicMock()
        mock_session.is_revoked = True
        mock_session.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        service.repo = AsyncMock()
        service.repo.get_by_token_hash = AsyncMock(return_value=mock_session)

        result = await service.validate_session(
            ValidateSessionRequest(refresh_token="some_token")
        )

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_validate_session_returns_false_for_expired(self):
        """Validating an expired session must return valid=False."""
        mock_db = AsyncMock()

        from app.services.session_service import SessionService
        from app.schemas.session import ValidateSessionRequest

        service = SessionService(mock_db)

        mock_session = MagicMock()
        mock_session.is_revoked = False
        mock_session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        mock_session.user_id = "uuid-123"
        mock_session.id = "session-uuid"
        service.repo = AsyncMock()
        service.repo.get_by_token_hash = AsyncMock(return_value=mock_session)

        result = await service.validate_session(
            ValidateSessionRequest(refresh_token="expired_token")
        )

        assert result.valid is False

    @pytest.mark.asyncio
    async def test_validate_session_returns_true_for_valid(self):
        """Validating a valid session must return valid=True along with the user_id."""
        mock_db = AsyncMock()

        from app.services.session_service import SessionService
        from app.schemas.session import ValidateSessionRequest

        service = SessionService(mock_db)

        mock_session = MagicMock()
        mock_session.is_revoked = False
        mock_session.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        mock_session.user_id = "uuid-123"
        mock_session.id = "session-uuid"
        service.repo = AsyncMock()
        service.repo.get_by_token_hash = AsyncMock(return_value=mock_session)

        result = await service.validate_session(
            ValidateSessionRequest(refresh_token="valid_token")
        )

        assert result.valid is True
        assert result.user_id == "uuid-123"
        assert result.session_id == "session-uuid"