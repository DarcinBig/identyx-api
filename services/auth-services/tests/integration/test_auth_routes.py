"""Integration tests for auth-service routes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestRegisterEndpoint:

    @pytest.mark.asyncio
    async def test_register_returns_201(self, client, sample_user_data):
        """POST /auth/register must return 201 with the tokens."""
        with patch("app.services.auth_service.AuthService.register") as mock_register:
            mock_register.return_value = MagicMock(
                access_token="access_jwt",
                refresh_token="refresh_token",
                token_type="Bearer",
                expires_in=1799,
                user=MagicMock(
                    id="uuid-123",
                    email=sample_user_data["email"],
                    username=sample_user_data["username"],
                    is_verified=False,
                    avatar_url="https://example.com/avatar.png",
                    avatar_provider="default",
                ),
                model_dump=lambda: {
                    "access_token": "access_jwt",
                    "refresh_token": "refresh_token",
                    "token_type": "Bearer",
                    "expires_in": 1799,
                    "user": {
                        "id": "uuid-123",
                        "email": sample_user_data["email"],
                        "username": sample_user_data["username"],
                        "is_verified": False,
                        "avatar_url": "https://example.com/avatar.png",
                        "avatar_provider": "default",
                    }
                }
            )

            response = await client.post("/auth/register", json=sample_user_data)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_register_missing_email(self, client):
        """POST /auth/register without an email must return 422."""
        response = await client.post("/auth/register", json={
            "username": "testuser",
            "password": "TestPassword@1",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client):
        """POST /auth/register with a password that is too simple must return a 422 status code."""
        response = await client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "weak",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """POST /auth/login without a body must return 422."""
        response = await client.post("/auth/login", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client):
        """POST /auth/login with invalid credentials must return 401."""
        with patch("app.services.auth_service.AuthService.login") as mock_login:
            from fastapi import HTTPException
            mock_login.side_effect = HTTPException(
                status_code=401, detail="Invalid email or password."
            )

            response = await client.post("/auth/login", json={
                "email": "test@example.com",
                "password": "WrongPassword@1",
            })

        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]