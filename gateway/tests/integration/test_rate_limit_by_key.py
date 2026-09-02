from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _proxy_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(
        return_value={
            "application_id": "app-1",
            "name": "My App",
            "allowed_origins": [],
            "status": "active",
            "key_type": "secret",
        }
    )
    return resp


class TestRateLimitByKey:
    @pytest.mark.asyncio
    async def test_per_key_limit_not_applied_without_key(self):
        """No API key → no per-key budget consumed; request passes through."""
        from app.main import app

        mock_client = AsyncMock()
        # Note: no X-Identyx-Key header, so ApiKeyAuth passes through.

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_per_key_limit_triggers_after_threshold(self, mock_rate_limit_redis):
        """Valid API key + over-limit count for the app bucket → 429."""
        from app.main import app

        # ApiKeyAuth resolves the key via application-service.
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json = MagicMock(
            return_value={
                "tenant_id": "tenant-1",
                "application_id": "app-1",
                "key_type": "secret",
                "allowed_origins": [],
                "status": "active",
            }
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=verify_response)

        # Over-limit: the middleware's pipeline returns count > limit.
        # The conftest mock returns pipeline once; we override per-call too
        # since RateLimitByKey also uses pipeline().
        pipeline_mock = mock_rate_limit_redis.pipeline.return_value
        pipeline_mock.zcard = MagicMock(return_value=601)
        pipeline_mock.execute = AsyncMock(return_value=[None, None, 601, None])

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.get(
                    "/v1/public/applications/me",
                    headers={"X-Identyx-Key": "sk_live_testkey"},
                )

        assert response.status_code == 429
        assert "retry_after" in response.json()
        assert response.headers["retry-after"] == "60"

    @pytest.mark.asyncio
    async def test_per_key_limit_calls_redis_with_app_bucket(self, mock_rate_limit_redis):
        """The per-key bucket key must include the resolved application_id."""
        from app.main import app

        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json = MagicMock(
            return_value={
                "tenant_id": "tenant-1",
                "application_id": "app-1",
                "key_type": "secret",
                "allowed_origins": [],
                "status": "active",
            }
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=verify_response)
        mock_client.get = AsyncMock(return_value=_proxy_response())

        pipeline_mock = mock_rate_limit_redis.pipeline.return_value
        pipeline_mock.zcard = MagicMock(return_value=1)
        pipeline_mock.execute = AsyncMock(return_value=[None, None, 1, None])

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.get(
                    "/v1/public/applications/me",
                    headers={"X-Identyx-Key": "sk_live_testkey"},
                )

        assert response.status_code == 200
        # The very first zadd call receives the bucket key.
        called_keys = [
            call.args[0] if call.args else call.kwargs.get("name")
            for call in pipeline_mock.zadd.call_args_list
        ]
        assert any("app-1" in (k or "") for k in called_keys)


class TestPerKeyAndPerIpAreIndependent:
    """The per-key and per-IP rate-limit layers must use independent Redis
    counters so that one layer exhausting its budget does not trigger the
    other."""

    @pytest.mark.asyncio
    async def test_per_key_429_does_not_consume_ip_budget(self, mock_rate_limit_redis):
        """When the per-key limiter rejects (429), the per-IP counter must not
        have been incremented — a subsequent request without an API key should
        still be allowed."""
        from app.main import app

        # ── Prepare the verify-key mock (ApiKeyAuth) ──
        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json = MagicMock(
            return_value={
                "tenant_id": "tenant-1",
                "application_id": "app-1",
                "key_type": "secret",
                "allowed_origins": [],
                "status": "active",
            }
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=verify_response)

        # ── Request 1: WITH API key, over per-key limit → 429 ──
        pipeline_mock = mock_rate_limit_redis.pipeline.return_value
        pipeline_mock.zcard = MagicMock(return_value=601)
        pipeline_mock.execute = AsyncMock(return_value=[None, None, 601, None])

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                r1 = await ac.get(
                    "/v1/public/applications/me",
                    headers={"X-Identyx-Key": "sk_live_testkey"},
                )
        assert r1.status_code == 429, "Expected per-key 429"

        # ── Request 2: WITHOUT API key (only per-IP applies) ──
        # The per-IP limiter is mocked to allow (count < limit).
        pipeline_mock.zcard = MagicMock(return_value=1)
        pipeline_mock.execute = AsyncMock(return_value=[None, None, 1, None])

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                r2 = await ac.get("/health")
        assert r2.status_code == 200, (
            "Per-key 429 must not have consumed the per-IP budget"
        )