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
import hashlib
import hmac
import os
import subprocess
import time
import uuid

import httpx
import pytest

GATEWAY_URL = os.environ.get("IDENTYX_GATEWAY_URL", "http://localhost:8100")
API_BASE = f"{GATEWAY_URL}/v1"

# Purpose strings bound into the HMAC one-time-token signature.
PURPOSE_VERIFY = "email_verification"
PURPOSE_RESET = "password_reset"
PURPOSE_DELETE = "delete_account"
PURPOSE_CHANGE = "email_change"

# Docker access used only to mint/stage one-time tokens exactly as the
# auth-service + user-service do (there is no reachable inbox in CI).
AUTH_CONTAINER = os.environ.get("IDENTYX_AUTH_CONTAINER", "identyx-auth")
USERS_DB_CONTAINER = os.environ.get("IDENTYX_USERS_DB_CONTAINER", "identyx-db-users")
USERS_DB_NAME = os.environ.get("IDENTYX_USERS_DB_NAME", "identyx_users")


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


def _docker_available() -> bool:
    try:
        return subprocess.run(["docker", "version"], capture_output=True).returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _reset_rate_limits():
    """
    Best-effort reset of the per-IP rate-limit / brute-force counters (Redis
    DB 2) before the suite, so re-running it within the same minute does not
    trip spurious 429s on login/register. Requires the local Docker stack;
    silently skipped when it is unavailable (e.g. a remote gateway).
    """
    if not _docker_available():
        return
    subprocess.run(
        ["docker", "exec", "identyx-redis", "sh", "-c", 'redis-cli -a "$REDIS_PASSWORD" -n 2 FLUSHDB'],
        capture_output=True,
    )


_JWT_SECRET = None


def _jwt_secret() -> str:
    """JWT_SECRET_KEY from the running auth container (dev stack only)."""
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = subprocess.check_output(
            ["docker", "exec", AUTH_CONTAINER, "sh", "-c", "echo \"$JWT_SECRET_KEY\""],
            text=True,
        ).strip()
    return _JWT_SECRET


def _mint_token(user_id: str, purpose: str) -> str:
    """Same one-time token the auth-service generates: {uid}.{purpose}.{ts}.{hmac}."""
    ts = int(time.time())
    message = f"{user_id}.{purpose}.{ts}"
    sig = hmac.new(_jwt_secret().encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{sig}"


def _store_token_hash(table: str, user_id: str, raw_token: str, pending_email: str | None = None) -> None:
    """Insert the SHA-256 token hash into the user-service DB."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    if table == "email_changes":
        sql = (
            f"INSERT INTO {table} (id, user_id, pending_email, token_hash, expires_at) "
            f"VALUES ('{uuid.uuid4()}', '{user_id}', '{pending_email}', '{token_hash}', "
            f"now() + interval '24 hours')"
        )
    else:
        sql = (
            f"INSERT INTO {table} (id, user_id, token_hash, expires_at) "
            f"VALUES ('{uuid.uuid4()}', '{user_id}', '{token_hash}', now() + interval '24 hours')"
        )
    subprocess.run(
        ["docker", "exec", USERS_DB_CONTAINER, "psql", "-U", "identyx", "-d", USERS_DB_NAME, "-c", sql],
        check=True, capture_output=True, text=True,
    )


# Email-confirmed flows need Docker to stage their one-time tokens.
pytestmark_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker unavailable — cannot stage one-time tokens for email-confirmed flows",
)


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


class TestOneTimeTokenFlows:
    """
    Email-confirmed flows through the public gateway.

    These use the same purpose-bound HMAC one-time tokens the auth-service
    generates, staged into the user-service DB exactly as its internal store
    endpoints do (a reachable inbox is not available in CI). Each test mints a
    *fresh* token AFTER the triggering public call so a same-second collision
    with a request-generated token (1 s token granularity) cannot occur.
    """

    pytestmark = pytestmark_docker

    @staticmethod
    def _stage(purpose: str, table: str, user_id: str, pending_email: str | None = None) -> str:
        """Mint a *fresh* token a full second after the triggering call, then stage it.

        Tokens carry a 1-second-granularity timestamp, so minting in the same
        second as a request-generated token would collide on the unique token_hash
        constraint. Sleeping first guarantees a distinct timestamp.
        """
        time.sleep(1.1)
        token = _mint_token(user_id, purpose)
        _store_token_hash(table, user_id, token, pending_email=pending_email)
        return token

    def test_verify_email_and_replay_rejected(self):
        email = _unique_email()
        registered = _register(email)
        user_id = registered["user"]["id"]

        token = self._stage(PURPOSE_VERIFY, "email_verifications", user_id)

        ok = client.get("/auth/verify-email", params={"token": token})
        assert ok.status_code == 200, ok.text
        assert ok.json()["is_verified"] is True

        replay = client.get("/auth/verify-email", params={"token": token})
        assert replay.status_code == 400

    def test_password_reset_success_rotation(self):
        """REGRESSION: reset tokens must verify with their own purpose."""
        email = _unique_email()
        registered = _register(email)
        user_id = registered["user"]["id"]

        token = self._stage(PURPOSE_RESET, "password_resets", user_id)

        reset = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "ResetPassword@2026"},
        )
        assert reset.status_code == 200, reset.text

        old = client.post("/auth/login", json={"email": email, "password": "StrongPass!2026"})
        assert old.status_code == 401

        fresh = client.post("/auth/login", json={"email": email, "password": "ResetPassword@2026"})
        assert fresh.status_code == 200

    def test_password_reset_rejects_wrong_purpose(self):
        """A delete/verify token must NOT reset a password (purpose binding)."""
        email = _unique_email()
        registered = _register(email)
        user_id = registered["user"]["id"]

        token = self._stage(PURPOSE_VERIFY, "password_resets", user_id)  # wrong purpose

        reset = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "ResetPassword@2026"},
        )
        assert reset.status_code == 400

    def test_email_change_request_and_confirm(self):
        email = _unique_email()
        registered = _register(email)
        user_id = registered["user"]["id"]
        new_email = _unique_email("new")

        req = client.post(
            f"/users/{user_id}/email-change",
            json={"password": "StrongPass!2026", "new_email": new_email},
            headers=_auth_headers(registered["access_token"]),
        )
        assert req.status_code == 200, req.text

        token = self._stage(PURPOSE_CHANGE, "email_changes", user_id, pending_email=new_email)

        confirm = client.post("/auth/confirm-email-change", json={"token": token})
        assert confirm.status_code == 200, confirm.text

        login = client.post("/auth/login", json={"email": new_email, "password": "StrongPass!2026"})
        assert login.status_code == 200, login.text
        assert login.json()["user"]["email"] == new_email

    def test_deletion_request_and_confirm(self):
        email = _unique_email()
        registered = _register(email)
        user_id = registered["user"]["id"]

        req = client.post(
            f"/users/{user_id}/deletion-request",
            json={"password": "StrongPass!2026"},
            headers=_auth_headers(registered["access_token"]),
        )
        assert req.status_code == 200, req.text

        token = self._stage(PURPOSE_DELETE, "deletion_requests", user_id)

        confirm = client.post("/auth/confirm-deletion", json={"token": token})
        assert confirm.status_code == 200, confirm.text

        gone = client.post("/auth/login", json={"email": email, "password": "StrongPass!2026"})
        assert gone.status_code == 401

