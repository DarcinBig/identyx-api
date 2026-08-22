# Identyx V1.1.1 — API Documentation for Apidog

## Table of contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Importing the OpenAPI spec into Apidog](#3-importing-the-openapi-spec-into-apidog)
4. [Environments (dev / prod)](#4-environments-dev--prod)
5. [Authentication & token script](#5-authentication--token-script)
6. [Collection structure](#6-collection-structure)
7. [Complete endpoint reference](#7-complete-endpoint-reference)
8. [Error handling](#8-error-handling)
9. [Rate limiting](#9-rate-limiting)
10. [Known limitations of the generated spec](#10-known-limitations-of-the-generated-spec)
11. [Changelog V1.1.1](#11-changelog-v110)
12. [Maintenance](#12-maintenance)

---

## 1. Overview

Identyx exposes a public API through a **FastAPI gateway** that proxies to five
internal microservices (`auth`, `user`, `session`, `token`, `email`). All public
routes are versioned under `/v1` and use JSON. A sixth internal service —
`application-service` (`:8006`, third-party applications & API keys) — runs in
the stack; its gateway wiring is prepared (`APPLICATION_SERVICE_URL`) and its
`/v1/applications/*` routes are staged.

The gateway is a pass-through: request/response payloads are defined by the internal
services and are not re-declared in the OpenAPI specification. This document therefore
describes every operation (paths, methods, security, behavior), while the schemas and
complete request/response examples are provided in [section 7](#7-complete-endpoint-reference).

---

## 2. Prerequisites

- Apidog **≥ 2.2** (Desktop or Cloud) — https://apidog.com
- Stack up for generating the spec:
  ```bash
  docker compose -f infra/docker-compose.yml up -d
  ```
- Generated spec: `docs/api/openapi.json` (already committed; regenerate it at every release).

---

## 3. Importing the OpenAPI spec into Apidog

1. **Create the project**
   - Menu **“+” → New project → API** → name: `Identyx` → type: **OpenAPI**.
2. **Import the definition**
   - **Import** button (arrow icon) → **OpenAPI/Swagger**.
   - Pick the file `docs/api/openapi.json`, **or** the URL (dev):
     `http://localhost:8100/openapi.json`.
   - Options: uncheck *“Create automatic test cases”* (document first),
     check *“Keep operationIds”*.
3. **Verify the import**
   - The collection must contain **18 operations**:
     - `auth` (7): register, login, logout, refresh, verify-email, reset-password, resend-verification
     - `users` (7): me, user-id, update, delete, upload-avatar, avatar-url, reset-avatar
     - `sessions` (3): index, revoke-all, delete
     - `observability` (1): check (`/health`)
   - The 11 protected operations must show a **lock 🔒** (`HTTPBearer` scheme).

---

## 4. Environments (dev / prod)

Create two environments: **Icons → Manage environments → + Add**.

| Variable | Dev | Prod |
|----------|-----|------|
| `baseUrl` | `http://localhost:8100` | `https://api.identyx.io` |
| `accessToken` | *(filled by script)* | *(filled by script)* |
| `refreshToken` | *(filled by script)* | *(filled by script)* |

> The `{baseUrl}` values in requests use the environment variable.
> The spec `servers` field (`http://localhost:8100`) is only used as the default
> on first import.

---

## 5. Authentication & token script

Protected endpoints expect `Authorization: Bearer <access_token>`.

### 5.1 Post-response script (auto-token)

On **POST /v1/auth/login** (and **POST /v1/auth/register**), tab **Scripts → Execute**:

```js
// Store the token pair after login/register
let data = pm.response.json();
if (pm.response.code === 200 || pm.response.code === 201) {
    pm.environment.set("accessToken", data.access_token);
    pm.environment.set("refreshToken", data.refresh_token);
    console.log("Tokens stored");
}
```

### 5.2 Global header

In each protected folder (`users`, `sessions`, and `logout`), add a **folder global
header**:

| Key | Value |
|-----|-------|
| `Authorization` | `Bearer {{accessToken}}` |

### 5.3 Refresh script (optional, recommended)

Apidog can refresh an expired access token automatically via a **pre-request** script:

```js
// If the token is missing, refresh it with the stored refreshToken
if (!pm.environment.get("accessToken")) {
    let r = pm.sendRequest({
        url: pm.environment.get("baseUrl") + "/v1/auth/refresh",
        method: "POST",
        header: { "Content-Type": "application/json" },
        body: { mode: "raw", raw: JSON.stringify({ refresh_token: pm.environment.get("refreshToken") }) }
    });
    let body = r.json();
    pm.environment.set("accessToken", body.access_token);
    pm.environment.set("refreshToken", body.refresh_token);
}
```

---

## 6. Collection structure

After import, reorganize the collection into **folders** (aligned with the spec tags):

```
Identyx
├── Auth (public)
│   ├── POST /v1/auth/register            🔓
│   ├── POST /v1/auth/login               🔓
│   ├── POST /v1/auth/refresh             🔓
│   ├── GET  /v1/auth/verify-email        🔓  ?token=
│   ├── POST /v1/auth/reset-password      🔓
│   └── POST /v1/auth/resend-verification 🔓
├── Auth (protected)
│   └── POST /v1/auth/logout              🔒
├── Users  🔒
│   ├── GET    /v1/users/me
│   ├── GET    /v1/users/{user_id}
│   ├── PATCH  /v1/users/{user_id}
│   ├── DELETE /v1/users/{user_id}
│   ├── POST   /v1/users/{user_id}/avatar   (multipart)
│   ├── GET    /v1/users/{user_id}/avatar
│   └── DELETE /v1/users/{user_id}/avatar
├── Sessions  🔒
│   ├── GET    /v1/sessions/
│   ├── DELETE /v1/sessions/revoke-all
│   └── DELETE /v1/sessions/{session_id}
└── Operational
    └── GET /health  🔓
```

---

## 7. Complete endpoint reference

> The imported spec already contains the descriptions. This section provides the
> **real-world examples** (request/response bodies) to paste into each Apidog
> operation (tab **Example** / **Response model**), because the pass-through gateway
> does not generate them.

### 7.1 POST `/v1/auth/register`

**Description:** creates an account, starts the session and sends the verification email.

**Request** `application/json`:
```json
{
  "email": "user@example.com",
  "username": "user_2026",
  "password": "StrongPass!2026"
}
```
**Constraints:**
- `email`: valid email, normalized to lowercase. Duplicate → `409`.
- `username`: 3–50 chars, `[a-zA-Z0-9_-]`.
- `password`: ≥ 8 chars, with 1 uppercase, 1 digit, 1 punctuation.

**Response `201`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.…",
  "refresh_token": "…",
  "token_type": "Bearer",
  "user": {
    "id": "c6df21f4-7e1c-4f19-b9e6-e0015c3b6726",
    "email": "user@example.com",
    "username": "user_2026",
    "is_verified": false,
    "created_at": "2026-08-09T10:00:00Z",
    "updated_at": "2026-08-09T10:00:00Z"
  }
}
```
**Errors:** `422` (invalid body), `409` (email already registered).

---

### 7.2 POST `/v1/auth/login`

**Request**:
```json
{ "email": "user@example.com", "password": "StrongPass!2026" }
```
**Response `200`**: same shape as register (`access_token`, `refresh_token`,
`token_type`, `user`). Sends a “new device login” alert email when the device is unknown.

**Errors:** `401` (invalid credentials or locked-out IP), `422`.

---

### 7.3 POST `/v1/auth/refresh`

Rotates the refresh token (single-use).

**Request**:
```json
{ "refresh_token": "…" }
```
**Response `200`**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.…",
  "refresh_token": "…",
  "token_type": "Bearer"
}
```
**Errors:** `401` (revoked/expired/reused token), `422`.

---

### 7.4 GET `/v1/auth/verify-email`

**Request:** `?token=<verification token received by email>`
**Response `200`**:
```json
{ "message": "Email verified", "email": "user@example.com", "is_verified": true }
```
**Errors:** `400` (missing, invalid, expired **or already-used** token).

---

### 7.5 POST `/v1/auth/reset-password`

**Request**:
```json
{ "token": "<reset token>", "new_password": "NewStrong!2026" }
```
**Response `200`.** **Errors:** `400` (invalid token), `422`.

---

### 7.6 POST `/v1/auth/resend-verification`

**Request**:
```json
{ "email": "user@example.com" }
```
**Response `200`** — identical whether or not the email exists (**anti-enumeration**).

---

### 7.7 POST `/v1/auth/logout` 🔒

**Request:** header `Authorization: Bearer <access_token>` + body:
```json
{ "refresh_token": "…" }
```
**Response `200`.** The access token is blacklisted in Redis; the refresh token revokes
the session.

---

### 7.8 GET `/v1/users/me` 🔒

**Response `200`** — full user object:
```json
{
  "id": "c6df21f4-7e1c-4f19-b9e6-e0015c3b6726",
  "email": "user@example.com",
  "username": "user_2026",
  "is_verified": true,
  "created_at": "2026-08-09T10:00:00Z",
  "updated_at": "2026-08-09T10:00:00Z"
}
```

---

### 7.9 GET `/v1/users/{user_id}` 🔒

Reads a user profile. **Ownership:** the user themself or the account owner. Any other
account → `403`.

---

### 7.10 PATCH `/v1/users/{user_id}` 🔒

Partial update.

**Request**:
```json
{
  "username": "new_username",
  "first_name": "Ada",
  "last_name": "Lovelace"
}
```
**Response `200`** — updated user. **Errors:** `401`, `403`, `404`, `422`.

---

### 7.11 DELETE `/v1/users/{user_id}` 🔒

Permanent account deletion + revocation of all sessions.

---

### 7.12 POST `/v1/users/{user_id}/avatar` 🔒

Upload/replace the avatar. **Body `multipart/form-data`**: field `file` (PNG/JPEG image).

**Response `200`**:
```json
{
  "avatar_url": "https://…/avatars/c6df21f4….png",
  "avatar_provider": "github",
  "message": "Avatar updated"
}
```

---

### 7.13 GET `/v1/users/{user_id}/avatar` 🔒

**Response `200`**:
```json
{ "avatar_url": "https://…/avatars/c6df21f4….png", "avatar_provider": "github" }
```

---

### 7.14 DELETE `/v1/users/{user_id}/avatar` 🔒

Removes the avatar (falls back to the default).

---

### 7.15 GET `/v1/sessions/` 🔒

Lists the active sessions.

**Response `200`**:
```json
{
  "total": 2,
  "sessions": [
    {
      "id": "0f8f8f8f-…",
      "device_info": "Mozilla/5.0 … Chrome/126",
      "created_at": "2026-08-09T10:00:00Z"
    }
  ]
}
```

---

### 7.16 DELETE `/v1/sessions/revoke-all` 🔒

Signs out of **all** sessions. **Response `200`** (with the number of revoked sessions).

---

### 7.17 DELETE `/v1/sessions/{session_id}` 🔒

Revokes a single session. `403` if the session does not belong to the authenticated
user, `404` if it does not exist.

---

### 7.18 GET `/health`

Liveness probe (public).

**Response `200`**:
```json
{
  "service": "gateway",
  "status": "ok",
  "version": "1.1.1",
  "uptime_seconds": 1810,
  "services": {
    "auth-service": "ok",
    "user-service": "ok",
    "token-service": "ok",
    "session-service": "ok",
    "email-service": "ok"
  }
}
```
`status` is `ok` only when every service reports `ok`, otherwise `degraded`.

---

## 8. Error handling

| Code | Meaning | Typical body |
|------|---------|--------------|
| `400` | Invalid/expired/already-used token (email verification, reset) | `{"detail": "Verification token already used."}` |
| `401` | Missing, invalid, expired or revoked token; wrong credentials; locked-out IP | `{"detail": "…"}` |
| `403` | Not the owner (users/sessions ownership) | `{"detail": "Forbidden"}` |
| `404` | Resource not found | `{"detail": "Not Found"}` |
| `409` | Conflict (email already registered) | `{"detail": "Email already registered"}` |
| `422` | Invalid body / parameters (validation) | `HTTPValidationError` schema |
| `429` | Too many requests (rate limit) | `{"detail": "Rate limit exceeded", "retry_after": 12}` |
| `503` | Internal service unavailable | `{"error": "User service unavailable"}` |
| `504` | Internal service timeout | `{"error": "Auth service timeout"}` |

> **Important:** the `401/403` responses of protected routes and validation errors are
> emitted by the gateway **before** the proxy — their shape may therefore differ from
> the internal services. Document both shapes in Apidog (tab “Responses” of each
> operation).

---

## 9. Rate limiting

Applied by the gateway per **IP** (sliding 60 s window, Redis).

| Endpoint | Limit (default) | Variable |
|----------|-----------------|----------|
| Global (all routes) | 100 req/min | `RATE_LIMIT_GLOBAL` |
| `/v1/auth/login` | 10 req/min | `RATE_LIMIT_LOGIN` |
| `/v1/auth/register` | 5 req/min | `RATE_LIMIT_REGISTER` |
| `/v1/auth/reset-password` | 3 req/min | `RATE_LIMIT_RESET_PASSWORD` |
| `/v1/auth/verify-email` + `/resend-verification` | 5 req/min | `RATE_LIMIT_VERIFY_EMAIL` |

The `429` response includes `retry_after` (seconds). The brute-force protection
(auth-service) locks the IP after 5 failures for 15 minutes (`BRUTE_FORCE_MAX_ATTEMPTS`
/ `BRUTE_FORCE_LOCKOUT_MINUTES`).

---

## 10. Known limitations of the generated spec

| Limitation | Consequence | Mitigation |
|------------|-------------|------------|
| No request/response schemas (pass-through gateway) | Empty `requestBody`/`responses` after import | Add models + examples manually in Apidog (section 7) |
| The security scheme uses `auto_error=False` | Swagger UI does not require the header | The gateway JWT middleware still returns `401` — the real behavior is correct |
| `/v1/sessions/` with trailing slash in the spec | Canonical URL with `/` | Apidog accepts both (`/v1/sessions` works too) |
| Generated `operationId`s (`refresh-token`, `user-id`…) | Non-RPC names | Document the business names in Apidog |

---

## 11. Changelog V1.1.1

- **Infrastructure — healthchecks:** Prometheus (`/-/healthy`), Grafana
  (`/api/health`) and Tempo (`/ready`) now ship Docker HTTP healthchecks in both
  compose stacks (`infra/docker-compose.yml` and
  `infra/docker-compose.prod.yml`); in production Grafana waits for Prometheus
  to be healthy (`depends_on: service_healthy`).
- **application-service:** security fix — `verify-key` cache hits now re-validate
  the secret (`key_hash`) before returning `200` instead of trusting the cached
  payload; regression test added (61 unit tests passing). Memory limit raised to
  `256M` in the prod compose (fixes an OOM crash under load).
- **Gateway wiring prepared:** `APPLICATION_SERVICE_URL=http://application-service:8006`
  added to `.env`, `.env.example`, the gateway config (`application_service_url`)
  and both compose files; the `/v1/applications/*` proxy routes are staged for
  the next release.
- **Email change:** full workflow verified end-to-end (24/24 checks) — after
  confirmation the new email **replaces** `users.email` (the old address is not
  retained) and `is_verified` is set to `True`.

### Previous release (V1.0.0)

- **Versioning:** all public routes under `/v1`.
- **Security:** headers (HSTS, nosniff, frame DENY, referrer-policy, permissions-policy),
  `server` hidden, restricted CORS, JWT validated at the gateway, ownership on
  users/sessions, `X-User-Id`/`X-Forwarded-For` anti-spoofing, anti-enumeration on
  `resend-verification` and `login`.
- **Internal routes** (`/tokens/*`, `/users/internal/*`) not exposed publicly.
- **Docs disabled in prod:** `/docs`, `/redoc`, `/openapi.json` → `404` when
  `ENVIRONMENT=production`.
- **Sessions:** refresh token rotation, multi-device limit (the oldest session is
  revoked).
- **Email:** verification (single-use HMAC token), new-login alert, password reset —
  via Redpanda → email-service (SMTP Brevo).

---

## 12. Maintenance

```bash
# 1. Fix/enrich a description → in the code
#    gateway/app/routes/{auth,users,sessions}.py

# 2. Rebuild + re-export the spec
docker compose -f infra/docker-compose.yml up -d --build gateway
curl -s http://localhost:8100/openapi.json -o docs/api/openapi.json

# 3. In Apidog: Import → OpenAPI/Swagger → docs/api/openapi.json
#    Check “Merge with existing collection” to keep the examples,
#    scripts and models you already created.
```

> Release process: at each `v*` tag, the CI builds the GHCR images; the exported spec
> is committed with the tag to stay traceable. The Apidog documentation follows
> automatically via the re-import.
