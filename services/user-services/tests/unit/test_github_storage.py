"""Unit tests for the GitHub storage provider robustness (retry + shared client)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage.github_upload import GithHubStorageProvider


def _provider():
    with patch.object(
        GithHubStorageProvider, "__init__", lambda self: None
    ):
        provider = GithHubStorageProvider()
    provider.owner = "DarcinBig"
    provider.repo = "identyx-api"
    provider.branch = "main"
    provider.folder = "avatars"
    provider._client = MagicMock()
    return provider


class TestGitHubRetry:
    @pytest.mark.asyncio
    async def test_upload_retries_on_503_then_succeeds(self):
        provider = _provider()
        provider._get_file_sha = AsyncMock(return_value=None)

        transient = MagicMock()
        transient.status_code = 503
        ok = MagicMock()
        ok.status_code = 201
        ok.text = ""
        provider._client.request = AsyncMock(
            side_effect=[transient, transient, ok]
        )

        url = await provider.upload(b"data", "uuid-1.png", "image/png")

        assert url == "https://raw.githubusercontent.com/DarcinBig/identyx-api/main/avatars/uuid-1.png"
        assert provider._client.request.await_count == 3

    @pytest.mark.asyncio
    async def test_upload_gives_up_after_max_attempts(self):
        provider = _provider()
        provider._get_file_sha = AsyncMock(return_value=None)

        transient = MagicMock()
        transient.status_code = 500
        transient.text = "boom"
        provider._client.request = AsyncMock(return_value=transient)

        with pytest.raises(RuntimeError) as exc:
            await provider.upload(b"data", "uuid-1.png", "image/png")
        assert "GitHub upload failed" in str(exc.value)
        assert provider._client.request.await_count == 3

    @pytest.mark.asyncio
    async def test_upload_4xx_not_retried(self):
        provider = _provider()
        provider._get_file_sha = AsyncMock(return_value=None)

        forbidden = MagicMock()
        forbidden.status_code = 403
        forbidden.text = "forbidden"
        provider._client.request = AsyncMock(return_value=forbidden)

        with pytest.raises(RuntimeError):
            await provider.upload(b"data", "uuid-1.png", "image/png")
        assert provider._client.request.await_count == 1

    @pytest.mark.asyncio
    async def test_delete_retries_then_succeeds(self):
        provider = _provider()
        provider._get_file_sha = AsyncMock(return_value="abc123")

        transient = MagicMock()
        transient.status_code = 504
        ok = MagicMock()
        ok.status_code = 200
        provider._client.request = AsyncMock(side_effect=[transient, ok])

        deleted = await provider.delete("uuid-1.png")

        assert deleted is True
        assert provider._client.request.await_count == 2

    @pytest.mark.asyncio
    async def test_get_sha_not_found_returns_none(self):
        provider = _provider()
        not_found = MagicMock()
        not_found.status_code = 404
        provider._client.request = AsyncMock(return_value=not_found)

        sha = await provider._get_file_sha("missing.png")

        assert sha is None
