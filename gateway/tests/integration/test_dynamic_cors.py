from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _proxy_response():
    """A mock response for the application-service /applications/me proxy."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(
        return_value={
            "application_id": "app-1",
            "name": "My App",
            "allowed_origins": ["https://my-app.example.com"],
            "status": "active",
            "key_type": "secret",
        }
    )
    return resp


class TestDynamicCorsPreflight:
    @pytest.mark.asyncio
    async def test_preflight_allowed_static_origin(self):
        """Origin in CORS_ORIGINS → 200 + CORS headers, no service call."""
        from app.main import app

        mock_client = AsyncMock()
        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.request(
                    "OPTIONS",
                    "/v1/public/applications/me",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "GET",
                    },
                )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "x-identyx-key" in response.headers["access-control-allow-headers"].lower()
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_preflight_allowed_dynamic_origin(self):
        """Origin registered by an app → resolved via application-service."""
        from app.main import app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"allowed": True, "applications": ["app-1"]})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.request(
                    "OPTIONS",
                    "/v1/public/applications/me",
                    headers={
                        "Origin": "https://my-app.example.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"]
            == "https://my-app.example.com"
        )
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_preflight_disallowed_origin(self):
        """Unknown origin → 400, no CORS headers."""
        from app.main import app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"allowed": False, "applications": []})
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.request(
                    "OPTIONS",
                    "/v1/public/applications/me",
                    headers={
                        "Origin": "https://evil.example.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers

    @pytest.mark.asyncio
    async def test_preflight_resolution_failure_is_denied(self):
        """application-service unreachable at preflight → fail closed (400)."""
        from app.main import app

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("boom"))

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.request(
                    "OPTIONS",
                    "/v1/public/applications/me",
                    headers={
                        "Origin": "https://my-app.example.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
        assert response.status_code == 400


class TestDynamicCorsActualRequest:
    @pytest.mark.asyncio
    async def test_actual_request_sets_allow_origin_for_key_auth(self):
        """After ApiKeyAuth resolves an app, its origin is allowed."""
        from app.main import app

        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.json = MagicMock(
            return_value={
                "tenant_id": "tenant-1",
                "application_id": "app-1",
                "key_type": "secret",
                "allowed_origins": ["https://my-app.example.com"],
                "status": "active",
            }
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=verify_response)
        mock_client.get = AsyncMock(return_value=_proxy_response())

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as async_client:
                response = await async_client.get(
                    "/v1/public/applications/me",
                    headers={
                        "X-Identyx-Key": "sk_live_testkey",
                        "Origin": "https://my-app.example.com",
                    },
                )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"]
            == "https://my-app.example.com"
        )