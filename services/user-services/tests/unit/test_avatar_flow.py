"""Unit tests for user-service avatar and account flows."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.user_service import UserService

settings = get_settings()
DEFAULT_AVATAR = settings.get_default_avatar_url()


def _make_user(**overrides):
    """Build a User model-like object with the minimal fields used by the service."""
    user = MagicMock()
    user.id = "uuid-123"
    user.email = "user@example.com"
    user.username = "user"
    user.is_active = True
    user.is_verified = False
    user.avatar_url = None
    user.avatar_provider = "default"
    user.created_at = MagicMock()
    user.updated_at = MagicMock()
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


def _service(db=None, storage=None):
    svc = UserService(db or AsyncMock())
    svc.storage = storage if storage is not None else AsyncMock()
    return svc


class TestCreateUserAvatar:
    """A new account must always resolve to the default avatar, never upload."""

    @pytest.mark.asyncio
    async def test_create_user_resolves_default_avatar(self):
        db = AsyncMock()
        svc = _service(db)
        svc.repo.get_by_email = AsyncMock(return_value=None)
        svc.repo.get_by_username = AsyncMock(return_value=None)
        svc.repo.create = AsyncMock(return_value=_make_user())

        from app.schemas.user import UserCreate

        result = await svc.create_user(
            UserCreate(email="user@example.com", username="user", password="StrongPass!2026")
        )

        assert result.avatar_url == DEFAULT_AVATAR
        assert result.avatar_provider == "default"
        # No storage write must ever happen at signup
        svc.storage.upload_avatar.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email_409(self):
        db = AsyncMock()
        svc = _service(db)
        svc.repo.get_by_email = AsyncMock(return_value=_make_user())

        from app.schemas.user import UserCreate

        with pytest.raises(HTTPException) as exc:
            await svc.create_user(
                UserCreate(email="user@example.com", username="other", password="StrongPass!2026")
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username_409(self):
        db = AsyncMock()
        svc = _service(db)
        svc.repo.get_by_email = AsyncMock(return_value=None)
        svc.repo.get_by_username = AsyncMock(return_value=_make_user())

        from app.schemas.user import UserCreate

        with pytest.raises(HTTPException) as exc:
            await svc.create_user(
                UserCreate(email="other@example.com", username="user", password="StrongPass!2026")
            )
        assert exc.value.status_code == 409


class TestDeleteUserAvatarCleanup:
    """Deleting an account must remove an uploaded avatar from storage."""

    @pytest.mark.asyncio
    async def test_delete_user_with_uploaded_avatar_deletes_storage_file(self):
        db = AsyncMock()
        storage = AsyncMock()
        svc = _service(db, storage)
        svc.repo.get_by_id = AsyncMock(return_value=_make_user(avatar_provider="upload"))
        svc.repo.delete = AsyncMock(return_value=True)

        result = await svc.delete_user("uuid-123")

        assert result == {"message": "User deleted successfully"}
        storage.delete_avatar.assert_awaited_once_with("uuid-123")
        svc.repo.delete.assert_awaited_once_with("uuid-123")

    @pytest.mark.asyncio
    async def test_delete_user_with_default_avatar_skips_storage(self):
        db = AsyncMock()
        storage = AsyncMock()
        svc = _service(db, storage)
        svc.repo.get_by_id = AsyncMock(return_value=_make_user(avatar_provider="default"))
        svc.repo.delete = AsyncMock(return_value=True)

        await svc.delete_user("uuid-123")

        storage.delete_avatar.assert_not_called()
        svc.repo.delete.assert_awaited_once_with("uuid-123")

    @pytest.mark.asyncio
    async def test_delete_user_unknown_404(self):
        db = AsyncMock()
        svc = _service(db)
        svc.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await svc.delete_user("uuid-404")
        assert exc.value.status_code == 404


class TestAvatarLifecycle:
    """upload_avatar → get_avatar_url → delete_avatar (reset to default)."""

    @pytest.mark.asyncio
    async def test_upload_avatar_returns_url_and_sets_provider_upload(self):
        db = AsyncMock()
        storage = AsyncMock()
        storage.upload_avatar = AsyncMock(return_value="https://raw.githubusercontent.com/x/y.png")
        svc = _service(db, storage)
        svc.repo.get_by_id = AsyncMock(return_value=_make_user())
        svc.repo.update_avatar = AsyncMock(return_value=_make_user())

        file = MagicMock()
        file.content_type = "image/png"

        result = await svc.upload_avatar("uuid-123", file)

        assert result.avatar_provider == "upload"
        assert result.avatar_url.endswith(".png")
        svc.repo.update_avatar.assert_awaited_once_with(
            user_id="uuid-123",
            avatar_url="https://raw.githubusercontent.com/x/y.png",
            avatar_provider="upload",
        )

    @pytest.mark.asyncio
    async def test_get_avatar_url_default_resolution(self):
        db = AsyncMock()
        svc = _service(db)
        svc.repo.get_by_id = AsyncMock(return_value=_make_user(avatar_provider="default"))

        result = await svc.get_avatar_url("uuid-123")

        assert result.avatar_url == DEFAULT_AVATAR
        assert result.avatar_provider == "default"

    @pytest.mark.asyncio
    async def test_delete_avatar_resets_to_default(self):
        db = AsyncMock()
        storage = AsyncMock()
        svc = _service(db, storage)
        svc.repo.get_by_id = AsyncMock(
            return_value=_make_user(
                avatar_provider="upload",
                avatar_url="https://raw.githubusercontent.com/x/y.png",
            )
        )
        svc.repo.update_avatar = AsyncMock(return_value=_make_user(avatar_provider="default"))

        result = await svc.delete_avatar("uuid-123")

        storage.delete_avatar.assert_awaited_once_with("uuid-123")
        assert result.avatar_url == DEFAULT_AVATAR
        assert result.avatar_provider == "default"
