from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


class TestPublicRoutes:
    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as async_client:
            response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_protected_route_with_invalid_jwt_returns_401(self):
        from app.main import app

        # Mock HTTP client – json() must be synchronous
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"valid": False})
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.http.client", mock_client):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as async_client:
                response = await async_client.get(
                    "/users/me",
                    headers={"Authorization": "Bearer invalid.token.here"}
                )

        assert response.status_code == 401

class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_health_response_has_security_headers(self):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as async_client:
            response = await async_client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_rate_limit_triggers_after_threshold(self, mock_rate_limit_redis):
        from app.main import app

        pipeline_mock = mock_rate_limit_redis.pipeline.return_value
        pipeline_mock.zcount = MagicMock(return_value=11)
        pipeline_mock.execute = AsyncMock(return_value=[None, None, 11, None])

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "wrong"}
            )

        assert response.status_code == 429
        assert "retry_after" in response.json()