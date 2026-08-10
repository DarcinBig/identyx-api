"""
End-to-end tests against a running Identyx stack.

These tests exercise the whole public API through the gateway
(versioned under /v1) — the same path a frontend would use.

Prerequisites:
    - The stack must be running:
        cd infra && docker compose up -d --build
    - The API must be reachable at IDENTYX_GATEWAY_URL
      (default http://localhost:8100).

Run:
    pytest tests/e2e

If the gateway is unreachable, every test is skipped automatically.

Note on rate limiting: /v1/auth/register is limited to 5 req/min per IP.
Re-running the suite within the same minute may return 429 —
wait a minute or raise RATE_LIMIT_REGISTER in the root .env.
"""
import os
import uuid

import httpx
import pytest

GATEWAY_URL = os.environ.get("IDENTYX_GATEWAY_URL", "http://localhost:8100")
API_BASE = f"{GATEWAY_URL}/v1"


def _gateway_alive() -> bool:
    try:
        return httpx.get(f"{GATEWAY_URL}/health", timeout=3).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gateway_alive(),
    reason="Gateway unreachable — start the stack first (infra/docker-compose.yml)",
)

# /v1 API client — used for everything that goes through the public API.
client = httpx.Client(base_url=API_BASE, timeout=20)

# Root client — only for unversioned operational endpoints (/health).
root_client = httpx.Client(base_url=GATEWAY_URL, timeout=20)


def _unique_email(prefix: str = "e2e") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:12]}@example.com"


def _register(email: str, username: str | None = None) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username or f"user_{uuid.uuid4().hex[:8]}",
            "password": "StrongPass!2026",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


class TestHealth:
    def test_health_all_services_ok(self):
        response = root_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "gateway"
        assert body["status"] == "ok"
        assert all(v == "ok" for v in body["services"].values()), body["services"]


class TestPublicApi:
    def test_internal_routes_not_exposed_through_gateway(self):
        """/tokens/* and /users/internal/* are internal — not publicly reachable."""
        # The gateway only exposes /v1/* + operational endpoints. Any other path
        # requires a JWT (401 without token) or does not exist (404).
        assert client.post("/tokens/generate", json={"user_id": "x"}).status_code in (401, 404)
        assert client.post("/tokens/revoke", json={"access_token": "x"}).status_code in (401, 404)
        assert client.get("/users/internal/by-email", params={"email": "a@b.c"}).status_code in (401, 404)
        assert client.post("/users/", json={}).status_code in (401, 404)

    def test_register_requires_valid_body(self):
        response = client.post(
            "/auth/register",
            json={"email": "not-an-email", "username": "u", "password": "weak"},
        )
        assert response.status_code == 422

    def test_login_wrong_password_returns_401(self):
        email = _unique_email()
        _register(email)
        response = client.post(
            "/auth/login",
            json={"email": email, "password": "WrongPass!9999"},
        )
        assert response.status_code == 401

    def test_login_unknown_email_returns_401(self):
        response = client.post(
            "/auth/login",
            json={"email": _unique_email("ghost"), "password": "Whatever!123"},
        )
        assert response.status_code == 401


class TestAuthFlow:
    def test_register_login_refresh_me_sessions_logout(self):
        email = _unique_email()
        registered = _register(email)
        access_token = registered["access_token"]
        refresh_token = registered["refresh_token"]
        user_id = registered["user"]["id"]
        assert registered["token_type"] == "Bearer"
        assert registered["user"]["email"] == email

        # Login again
        login = client.post(
            "/auth/login",
            json={"email": email, "password": "StrongPass!2026"},
        )
        assert login.status_code == 200, login.text
        login_body = login.json()
        assert login_body["user"]["id"] == user_id

        # Refresh rotates the pair
        refreshed = client.post(
            "/auth/refresh",
            json={"refresh_token": login_body["refresh_token"]},
        )
        assert refreshed.status_code == 200, refreshed.text
        refreshed_body = refreshed.json()
        assert refreshed_body["access_token"]

        # Current profile
        me = client.get("/users/me", headers=_auth_headers(access_token))
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email

        # Sessions are listed
        sessions = client.get("/sessions", headers=_auth_headers(access_token))
        assert sessions.status_code == 200, sessions.text
        assert sessions.json()["total"] >= 1

        # Logout revokes the session + blacklists the access token
        logout = client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
            headers=_auth_headers(access_token),
        )
        assert logout.status_code == 200, logout.text

        # Old refresh token is dead after logout
        stale = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert stale.status_code == 401

    def test_duplicate_email_conflict(self):
        email = _unique_email()
        _register(email)
        second = client.post(
            "/auth/register",
            json={
                "email": email.upper(),  # normalization: same email → 409
                "username": f"user_{uuid.uuid4().hex[:8]}",
                "password": "StrongPass!2026",
            },
        )
        assert second.status_code == 409, second.text

    def test_resend_verification_does_not_disclose_existing_email(self):
        email = _unique_email()
        _register(email)
        response = client.post("/auth/resend-verification", json={"email": email})
        assert response.status_code == 200
        ghost = client.post("/auth/resend-verification", json={"email": _unique_email("ghost")})
        assert ghost.status_code == 200
        assert response.json() == ghost.json()


class TestAuthorization:
    def test_protected_route_requires_token(self):
        assert client.get("/users/me").status_code == 401
        assert client.get("/sessions").status_code == 401

    def test_invalid_token_rejected(self):
        response = client.get(
            "/users/me", headers={"Authorization": "Bearer garbage.token.here"}
        )
        assert response.status_code == 401

    def test_x_user_id_spoofing_is_rejected(self):
        """The gateway must ignore a caller-supplied X-User-Id header."""
        email = _unique_email()
        registered = _register(email)
        me = client.get(
            "/users/me",
            headers={
                **_auth_headers(registered["access_token"]),
                "X-User-Id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert me.status_code == 200
        assert me.json()["id"] == registered["user"]["id"]

    def test_ownership_prevents_cross_user_access(self):
        user_a = _register(_unique_email("a"))
        user_b = _register(_unique_email("b"))

        a_id = user_a["user"]["id"]
        headers_b = _auth_headers(user_b["access_token"])

        assert client.get(f"/users/{a_id}", headers=headers_b).status_code == 403
        assert (
            client.patch(
                f"/users/{a_id}",
                json={"username": "hijacked"},
                headers=headers_b,
            ).status_code
            == 403
        )
        assert (
            client.request(
                "DELETE",
                f"/users/{a_id}",
                json={"password": "StrongPass!2026"},
                headers=headers_b,
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/users/{a_id}/avatar",
                files={"file": ("x.png", b"not-an-image", "image/png")},
                headers=headers_b,
            ).status_code
            in (403, 422)
        )

        # The real owner can read their own profile
        me = client.get("/users/me", headers=_auth_headers(user_a["access_token"]))
        assert me.status_code == 200
        assert me.json()["id"] == a_id
