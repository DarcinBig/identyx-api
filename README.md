# Identyx

```
 ___    _            _              
|_ _|__| | ___ _ __ | |_ _   ___  __
 | |/ _` |/ _ \ '_ \| __| | | \ \/ /
 | | (_| |  __/ | | | |_| |_| |>  < 
|___\__,_|\___|_| |_|\__|\__, /_/\_\
                         |___/      
```

> Authentication & Identity API — **V1.1.3**

[![CI](https://github.com/DarcinBig/identyx-api/actions/workflows/ci.yml/badge.svg)](https://github.com/DarcinBig/identyx-api/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-059487?logo=fastapi)](https://fastapi.tiangolo.com)

**Identyx** is a production-ready authentication and identity platform built with
**FastAPI** and a **microservices architecture**. It provides email/password
authentication, JWT token rotation, session management, email verification,
password reset and transactional email alerts — designed for security,
scalability and seamless integration across web and mobile applications.

### Features

| Feature | Status |
|---|---|
| **Email / Password auth** | ✅ Done |
| **Email verification (HMAC one-time tokens)** | ✅ Done |
| **JWT access + refresh tokens with rotation** | ✅ Done |
| **Session management & revocation** | ✅ Done |
| **Multi-device session limit (oldest revoked)** | ✅ Done |
| **User profile management & avatars** | ✅ Done |
| **Transactional emails via Kafka/Redpanda** | ✅ Done |
| **New-login alerts (device + IP geolocation)** | ✅ Done |
| **Brute-force protection & suspicious-login alerts** | ✅ Done |
| **GDPR account deletion (email-confirmed)** | ✅ Done |
| **Email change with re-verification** | ✅ Done |
| **Email change notification (new address)** | ✅ Done |
| **Password confirmation on sensitive actions** | ✅ Done |
| **Multi-tenancy (tenant-scoped isolation)** | ✅ Done |
| **TRUST_PROXY for correct IP detection behind reverse proxies** | ✅ Done |
| **Prometheus metrics + Grafana dashboards** | ✅ Done |
| **OpenTelemetry distributed traces (Tempo)** | ✅ Done |
| **Third-party application registry & API keys** | ✅ Done |
| **API key authentication (X-Identyx-Key)** | ✅ Done |
| **Dynamic per-application CORS (resolve-by-origin)** | ✅ Done |
| **Rate limiting by API key (per route group)** | ✅ Done |
| **CI: lint, unit tests, E2E suite** | ✅ Done |
| **OAuth 2.0 providers (Google, GitHub, …)** | 🔜 Planned |
| **Passkeys (WebAuthn)** | 🔜 Planned |
| **Multi-factor authentication (MFA / TOTP)** | 🔜 Planned |

---

## Architecture

### 1. System overview

Identyx follows an **API Gateway + microservices** pattern. A single gateway is
the only externally reachable component; it authenticates every request and
proxies it to one of **6 services**, each owning its own data store. The
`application-service` (`:8006`) powers the third-party application registry and
API key infrastructure, wired into the gateway via `ApiKeyAuthMiddleware` and
`DynamicCORSMiddleware`; its public proxy route (`/v1/public/applications/me`)
is live.

```
                                        ┌─────────────────────┐
                                        │       CLIENTS       │
                                        │  Web · Mobile · CLI │
                                        └──────────┬──────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 GATEWAY  ·  :8100                                           │
│                                                                                             │
│   SecurityHeaders → RateLimit → Metrics → CORS → ApiKeyAuth → RateLimitByKey → JWTAuth      │
│   → Logging → Errors → Router                                                               │
│                                                                                             │
│   · Redis sliding-window rate limiting (per IP + per API key, per route group)              │
│   · Dynamic per-application CORS (preflight → resolve-by-origin, GIN-indexed)               │
│   · API key resolution via application-service (X-Identyx-Key header)                       │
│   · JWT validation via token-service + X-User-Id injection                                  │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────────────────────────────┘
       │          │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼          ▼
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐
  │  AUTH  │ │  USER  │ │ TOKEN  │ │SESSION │ │  EMAIL │ │APPLICATION │
  │ :8002  │ │ :8001  │ │ :8003  │ │ :8004  │ │ :8005  │ │   :8006    │
  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └──────┬─────┘
      │          │          │          │          │             │
      ▼          ▼          ▼          ▼          │             ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │       ┌─────────┐
  │ postgres│ │ postgres│ │ redis   │ │ postgres│ │       │ postgres│
  │  -auth  │ │  -users │ │  DB 0   │ │-sessions│ │       │  -apps  │
  └─────────┘ └─────────┘ └─────────┘ └─────────┘ │       └─────────┘
                                                  │
                                        ┌─────────┘
                                        ▼
                               ┌────────────────┐
                               │    Redpanda    │
                               │   (Kafka)      │
                               └───────┬────────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │  SMTP (Brevo)  │
                              └────────────────┘
```

**Message flow in a nutshell:**

1. A request enters the gateway on `:8100`.
2. The gateway applies the middleware chain (security headers, rate limit,
   metrics, API key resolution, JWT auth, CORS, logging, error handling).
3. If `X-Identyx-Key` is present, the gateway resolves it via the
   application-service and injects `X-Tenant-Id` + `X-Application-Id`.
4. For protected routes, the gateway validates the JWT through the
   **token-service** (`POST /tokens/verify`) and injects `X-User-Id`.
5. The request is proxied to the owning service (`/v1/auth/*` → auth-service,
   `/v1/users/*` → user-service, `/v1/sessions/*` → session-service,
   `/v1/public/*` → application-service).
6. Services collaborate **synchronously** (HTTP + `X-Internal-Key`) for
   request/response operations and **asynchronously** (Kafka events) for
   notifications.

### 2. Component responsibilities

| Component | Port | Responsibility |
|---|---|---|
| **gateway** | `8100` | Single entry point: rate limiting, API key resolution, JWT validation, routing, CORS, metrics, security headers, `/health` + `/metrics` |
| **auth-service** | `8002` | Register, login, logout, token refresh, email verification, password reset, account deletion & email change (email-confirmed); Argon2id hashing, brute-force protection, purpose-bound HMAC tokens, event publishing |
| **user-service** | `8001` | User profiles, avatar upload (JPEG/PNG/WebP ≤ 5 MB), one-time token storage (verification, reset, deletion, email-change); internal endpoints for auth-service |
| **token-service** | `8003` | JWT generation, verification (incl. `iss`/`aud`) and blacklisting (Redis DB 0). Internal only |
| **session-service** | `8004` | Session lifecycle, single-use refresh-token rotation, multi-device limit (oldest session revoked) |
| **email-service** | `8005` | Consumes Kafka events and sends transactional emails (verification, security alert, new-login alert with IP geolocation, deletion & email-change confirmations, post-change notification) |
| **application-service** | `8006` | Third-party application registry + API keys (`pk_live_…` / `sk_live_…`, Stripe-aligned); Redis-cached key verification (DB 3) with active cache invalidation on revoke. Proxied through gateway `/v1/public/*` |
| **redpanda** | `9092` | Kafka-compatible message broker for async events |
| **redis** | `6379` | Token blacklist (DB 0), service state (DB 1), rate limiting & brute-force counters (DB 2), API-key resolution cache (DB 3) |
| **postgres-\*** | `5432` | One isolated PostgreSQL instance per service (auth, users, sessions, applications) |
| **prometheus** | `9090` | Metrics collection and scraping |
| **grafana** | `3000` | Auto-provisioned dashboards (Prometheus datasource) |
| **tempo** | `4317/4318` | Distributed traces collector (OTLP) + query UI `3200` |

### 3. Gateway request pipeline

Pure-ASGI middleware wrapping, **outside → inside**:

```
SecurityHeaders → RateLimit → Metrics → _app (CORS → ApiKeyAuth → RateLimitByKey → JWTAuth → Errors → Logging → Router)
```

| Layer | Role |
|---|---|
| `SecurityHeadersMiddleware` | Sets hardening headers on every response |
| `RateLimitMiddleware` | Redis sliding-window per IP; tuned per route group (login `10/min`, register `5/min`, reset-password `3/min`, verify-email/resend `5/min`, refresh `20/min`, sessions `60/min`, everything else `100/min`) → `429` with `Retry-After` |
| `MetricsMiddleware` | Request counters/durations for Prometheus |
| `DynamicCORSMiddleware` | Per-application CORS: OPTIONS preflights resolved against application-service `GET /applications/resolve-by-origin` (GIN-indexed); actual responses use the resolved app `allowed_origins`, with a static `CORS_ORIGINS` fallback. Always allows `CORS_ORIGINS` |
| `ApiKeyAuthMiddleware` | Resolves `X-Identyx-Key` via application-service `/applications/verify-key`; injects `X-Tenant-Id` + `X-Application-Id` + `allowed_origins` into scope; skips JWT for API-key-only routes |
| `RateLimitByKeyMiddleware` | Redis sliding-window per route group (`ratekey:{application_id}:{path_group}`), `RATE_LIMIT_PER_KEY_RPM` (default `600/min` per group), in parallel with the per-IP limit → `429` + `Retry-After` |
| `JWTAuthMiddleware` | Extracts `Bearer` token, calls `POST /tokens/verify`, injects `X-User-Id`, strips caller-supplied `X-User-Id` / `X-Internal-Key` / `X-Identyx-Key` |
| `LoggingMiddleware` | Structured JSON request logs |
| `ErrorHandlingMiddleware` | Normalized JSON error responses |

The `/health` endpoint probes all 6 gateway-proxied services concurrently and reports
`ok`/`degraded`. The `/ready` endpoint additionally checks the rate-limit Redis
connection and returns `200`/`503` for orchestrator readiness probes.

### 4. Inter-service communication

**Synchronous (HTTP, request/response)** — always on the internal Docker network,
never exposed:

- Gateway → token-service: `POST /tokens/verify`
- auth-service → user-service: profile creation, `GET /users/internal/by-email`,
  `GET /users/internal/by-id`, verification & reset-token endpoints
- auth-service → token-service: `POST /tokens/generate`, `POST /tokens/revoke`
- auth-service → session-service: `POST /sessions/create`, `validate`, `rotate`,
  `revoke`, `internal/revoke-all`

All internal calls are authenticated with the shared `INTERNAL_API_KEY`
(`X-Internal-Key` header). The gateway strips this header from any external
request (defense in depth).

**Asynchronous (Kafka events)** — publishes on Redpanda; consumed by email-service:

| Topic | Emitted on | Consumed by |
|---|---|---|
| `user.registered` | Registration / verification re-send | email-service → verification email |
| `auth.login` | Successful login | (analytics-ready) |
| `auth.new_login` | Login from a new device | email-service → new-login alert (device + IP geolocation) |
| `auth.suspicious` | Login after near-lockout failures | email-service → security alert + reset link |
| `user.deletion_requested` | Account deletion requested | email-service → confirmation link (24 h, single use) |
| `user.email_change_requested` | Email change requested | email-service → confirmation link to the **new** address (24 h, single use) |
| `user.email_changed` | Email change confirmed | email-service → notification email to the new address |

The event stream decouples the auth-service from email delivery: if the
email-service is down, messages persist in Redpanda and are consumed later.

### 5. Data ownership

Each service owns **its** database and never writes to another service's store:

```
┌──────────────┬─────────────────────────┬───────────────────────────────┐
│ Service      │ Store                   │ Data                          │
├──────────────┼─────────────────────────┼───────────────────────────────┤
│ auth-service │ postgres-auth           │ credentials (Argon2id hashes) │
│ user-service │ postgres-users          │ profiles, avatars, token hashes, pending_email │
│ session-service│ postgres-sessions     │ sessions, refresh-token hashes │
│ token-service │ redis DB 0             │ access-token blacklist        │
│ gateway      │ redis DB 2              │ rate-limit sliding windows    │
│ auth-service │ redis DB 2              │ brute-force counters          │
│ email-service│ (SMTP) / redpanda       │ email templates, event stream │
│ application-service │ postgres-applications │ applications, API keys (key_id + SHA-256 key_hash) │
│ application-service │ redis DB 3             │ API-key resolution cache (TTL 60 s, active invalidation) │
└──────────────┴─────────────────────────┴───────────────────────────────┘
```

> One-time tokens (email verification, password reset, account deletion,
> email change) are stored in the user-service **only as SHA-256 hashes**; the
> raw token is HMAC-signed on the auth-service side and bound to a `purpose`, so
> a DB leak alone cannot forge a token and a token cannot be replayed across flows.

### 6. Security model

| Control | Where | Detail |
|---|---|---|
| **Password hashing** | auth-service | Argon2id (with silent rehash on param upgrades) |
| **JWT** | token-service | HS256, signed with `JWT_SECRET_KEY`; `iss=identyx`, `aud=identyx-api`; access token `30 min`, refresh token `7 days` |
| **Refresh-token rotation** | session-service | Refresh tokens are single-use; each refresh rotates the hash, so a stolen token is invalidated on first use |
| **Brute-force protection** | auth-service | 5 failed attempts → 15 min lockout (Redis DB 2, tenant-scoped keys); near-threshold logins raise a `auth.suspicious` alert |
| **Password confirmation** | gateway → auth-service | Delete-account, email-change and avatar-delete require the current password (`422` if missing, `403` if wrong) |
| **Account deletion (GDPR)** | auth-service + user-service | Deletion is **email-confirmed**: a purpose-bound one-time token must be validated before the credential, profile and sessions are removed |
| **Email change** | auth-service + user-service | New email is stored as `pending_email` and only applied after a purpose-bound one-time token is confirmed (with uniqueness re-check); a notification email is sent to the new address after confirmation |
| **Anti-enumeration** | auth-service | Unknown email, wrong password and lockout all return the same generic `401`; resend-verification returns a generic message |
| **One-time tokens** | auth-service + user-service | HMAC signature bound to a `purpose` (`email_verification`, `password_reset`, `delete_account`, `email_change`) + SHA-256 stored hash + expiry (24 h) + single use; a token cannot be replayed across flows |
| **Internal API** | all services | `X-Internal-Key` shared secret; routes hidden from the OpenAPI schema |
| **Header stripping** | gateway | `X-User-Id`, `X-Internal-Key` and `X-Identyx-Key` are never trusted from the client |
| **Multi-device limit** | session-service | Default 5 sessions/user; the oldest session is revoked automatically |
| **API key authentication** | gateway → application-service | `X-Identyx-Key` resolved via `/applications/verify-key`; cache-first (Redis DB 3, 60 s TTL); constant-time hash comparison; active invalidation on revoke |

### 7. Observability

- **Metrics** — every service exposes `/metrics` (Prometheus); scrape config in
  `infra/prometheus/prometheus.yml`.
- **Dashboards** — Grafana is auto-provisioned at `:3000` (datasource
  `infra/grafana/provisioning/`, dashboard `infra/grafana/dashboards/`):
  request rate, error rate (5xx), p50/p95 latency and active requests per service.
- **Traces** — each service ships OpenTelemetry spans (OTLP/HTTP) to Tempo
  (`:4318`); every FastAPI route and outgoing HTTP call is auto-instrumented.
  Tracing is enabled via `OTEL_ENABLED`/`OTEL_EXPORTER_OTLP_ENDPOINT` and is a
  no-op otherwise.
- **Logs** — structured JSON via `python-json-logger` (`service_started`,
  `service_stopped`, per-request logs, security events).
- **Healthchecks** — every container ships a Docker healthcheck. Prometheus
  (`/-/healthy`), Grafana (`/api/health`) and Tempo (`/ready`) expose HTTP
  probes wired into both compose stacks; in production Grafana waits for
  Prometheus to be healthy (`depends_on: service_healthy`).

---

## User flows

All flows are exposed through the gateway at `http://localhost:8100`.
The `Component` column traces each step across the microservices.

### 1. Registration

```
POST /v1/auth/register
```

| Step | Action | Component |
|---|---|---|
| 1 | Validate payload (email, username, password rules) | gateway → auth-service |
| 2 | Create the user profile | auth-service → user-service |
| 3 | Hash the password (Argon2id) and store the credential | auth-service → postgres-auth |
| 4 | Generate the access/refresh token pair | auth-service → token-service |
| 5 | Create the session and store the refresh-token hash | auth-service → session-service |
| 6 | Generate an HMAC verification token, store its hash | auth-service → user-service |
| 7 | Publish `user.registered` | auth-service → redpanda |
| 8 | Consume the event and send the verification email | email-service → SMTP (Brevo) |
| 9 | Return `{access_token, refresh_token, user}` | gateway |

If step 3 fails, the created profile is rolled back (best-effort) to avoid an
orphan account.

### 2. Email verification

```
GET /v1/auth/verify-email?token=<one-time-token>
```

| Step | Action | Component |
|---|---|---|
| 1 | Verify the HMAC signature → `user_id` | auth-service |
| 2 | Check the stored hash (expiry + not used) | auth-service → user-service |
| 3 | Mark the token used and the email verified | auth-service → user-service |
| 4 | Return `{message, email, is_verified}` | gateway |

### 3. Login

```
POST /v1/auth/login
```

| Step | Action | Component |
|---|---|---|
| 0 | Check brute-force lockout (Redis DB 2) | auth-service |
| 1 | Fetch the profile by email (unknown → generic `401`) | auth-service → user-service |
| 2 | Fetch the credential and verify the password (Argon2id) | auth-service → postgres-auth |
| 3 | On failure: record attempt → lockout at 5 → `401` | auth-service → redis |
| 4 | On success: reset the failure counter, rehash if needed | auth-service |
| 5 | Generate the token pair | auth-service → token-service |
| 6 | Create the session | auth-service → session-service |
| 7 | Publish `auth.login` + `auth.new_login` | auth-service → redpanda |
| 8 | Send new-login alert (device + IP geolocation) | email-service |
| 9 | If the account was near lockout: publish `auth.suspicious` + send security alert with one-time reset link | auth-service → email-service |
| 10 | Return the token pair and profile | gateway |

### 4. Token refresh (rotation)

```
POST /v1/auth/refresh
```

| Step | Action | Component |
|---|---|---|
| 1 | Validate the refresh token (single-use) | auth-service → session-service |
| 2 | Fetch the profile | auth-service → user-service |
| 3 | Generate a **new** token pair | auth-service → token-service |
| 4 | Rotate the session hash (old refresh token is burned) | auth-service → session-service |
| 5 | Return the new token pair | gateway |

If an attacker replays a stolen refresh token first, the legitimate client gets a
`401` on its next refresh.

### 5. Logout

```
POST /v1/auth/logout
```

| Step | Action | Component |
|---|---|---|
| 1 | Revoke the session | auth-service → session-service |
| 2 | Blacklist the access token until its natural expiry | auth-service → token-service |
| 3 | Return `{message}` | gateway |

### 6. Password reset

```
POST /v1/auth/reset-password    # one-time HMAC token + new password
```

| Step | Action | Component |
|---|---|---|
| 1 | Verify the HMAC signature → `user_id` | auth-service |
| 2 | Check the stored hash (expiry + single use) | auth-service → user-service |
| 3 | Hash the new password (Argon2id) and update the credential | auth-service → postgres-auth |
| 4 | Mark the reset token as used | auth-service → user-service |
| 5 | Revoke **all** sessions (every device is disconnected) | auth-service → session-service |

The reset link is delivered through the `auth.suspicious` / reset email built by
the email-service.

### 7. Session management & multi-device limit

| Action | Endpoint | Detail |
|---|---|---|
| List active sessions | `GET /v1/sessions/` | Returns all sessions with device info |
| Revoke one session | `DELETE /v1/sessions/{session_id}` | Owner only |
| Revoke all sessions | `DELETE /v1/sessions/revoke-all` | Signs out every device |

When a new login pushes the session count above `MAX_SESSIONS_PER_USER`
(default 5), the **oldest** session is revoked automatically.

### 8. Profile & avatar

| Action | Endpoint | Detail |
|---|---|---|
| Get current profile | `GET /v1/users/me` | From `X-User-Id` |
| Get / update / delete profile | `GET/PATCH/DELETE /v1/users/{user_id}` | Owner only; delete is email-confirmed and revokes sessions |
| Upload / get / reset avatar | `POST/GET/DELETE /v1/users/{user_id}/avatar` | JPEG/PNG/WebP ≤ 5 MB; old photo replaced; delete requires the current password |

### 9. Account deletion (GDPR, email-confirmed)

Deletion is **not** immediate — the account is only removed after the owner
confirms via a one-time link sent by email (proof of possession, GDPR §17):

```
POST /v1/users/{user_id}/deletion-request   # + {"password": ...}
POST /v1/auth/confirm-deletion              # + {"token": ...}
```

| Step | Action | Component |
|---|---|---|
| 1 | Confirm the current password and ownership | gateway → auth-service |
| 2 | Generate a `delete_account` one-time token, store its hash, publish `user.deletion_requested` | auth-service → user-service → redpanda |
| 3 | Send the confirmation link (24 h, single use) | email-service |
| 4 | `POST /v1/auth/confirm-deletion` validates the token | gateway → auth-service |
| 5 | Delete the credential, revoke **all** sessions, publish `user.deleted` | auth-service → postgres-auth → session-service |
| 6 | Delete the profile + uploaded avatar, mark the token used | auth-service → user-service |

### 10. Email change (with re-verification)

The new address is stored as `pending_email` and only becomes active after the
confirmation link is opened (delivered to the **new** address):

```
POST /v1/users/{user_id}/email-change        # + {"password": ..., "new_email": ...}
GET  /v1/auth/confirm-email-change?token=...  # browser click (email link)
```

| Step | Action | Component |
|---|---|---|
| 1 | Confirm the current password + ownership; reject same/already-registered emails | gateway → auth-service |
| 2 | Generate an `email_change` one-time token, store its hash, publish `user.email_change_requested` | auth-service → user-service → redpanda |
| 3 | Send the confirmation link to the new address (24 h, single use) | email-service |
| 4 | `GET /v1/auth/confirm-email-change` extracts the token from the query string and validates it | gateway → auth-service |
| 5 | Apply the new email, mark it verified, mark the token used | auth-service → user-service |
| 6 | Publish `user.email_changed`; send a notification email to the new address confirming the change | auth-service → email-service |

---

## Project layout

```
identyx-api/
├── README.md                         # this file
├── LICENSE                           # MIT
├── pyproject.toml                    # root tooling (ruff, pytest)
├── Makefile                          # dev targets (lint, test, up, down, e2e…)
├── .pre-commit-config.yaml           # ruff hooks (lint + format)
├── .env.example                      # development environment template
├── .env.production.example           # production environment template
├── .github/workflows/ci.yml          # CI pipeline (lint, tests, E2E, images)
│
├── docs/
│   └── api/
│       ├── APIDOG.md                 # Apidog-compatible API documentation
│       └── openapi.json              # exported OpenAPI spec
│
├── scripts/
│   ├── seed_native_application.py # idempotent seed for identyx-native app
│   └── e2e_smoke_test.sh          # lightweight CLI E2E smoke test
│
├── infra/                            # deployment & infrastructure
│   ├── docker-compose.yml            # full development stack
│   ├── docker-compose.prod.yml       # standalone production stack (Caddy TLS)
│   ├── Caddyfile                     # HTTPS reverse proxy (production)
│   ├── backup.sh                     # scheduled database backups
│   ├── restore.sh                    # restore databases from a backup
│   ├── prometheus/prometheus.yml     # Prometheus scrape config
│   ├── tempo/tempo.yml               # Tempo (OTLP traces) config
│   ├── grafana/
│   │   ├── provisioning/
│   │   │   ├── datasources/          # Prometheus + Tempo datasources
│   │   │   └── dashboards/           # dashboard provider config
│   │   └── dashboards/               # Identyx service-overview dashboard
│   └── redis/redis.conf              # Redis configuration
│
├── gateway/                          # API Gateway — :8100
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── tests/
│   └── app/
│       ├── main.py                   # FastAPI app, middleware wiring, /health, /ready, /metrics
│       ├── deps.py                   # shared dependencies (bearer scheme)
│       ├── http.py                   # shared httpx client
│       ├── core/
│       │   ├── config.py             # pydantic-settings configuration
│       │   └── logging/config.py     # structured JSON logging
│   ├── middleware/
│   │   ├── security_headers.py   # hardening headers
│   │   ├── rate_limit.py         # Redis sliding-window limiting
│   │   ├── api_key_auth.py       # API key resolution (X-Identyx-Key)
│   │   ├── jwt_auth.py           # Bearer validation + X-User-Id injection
│   │   ├── cors.py               # CORS allow-list
│   │   ├── logging.py            # request logging
│   │   └── errors.py             # normalized errors
│   ├── metrics/prometheus.py     # Prometheus metrics
│   ├── observability/tracing.py  # OpenTelemetry setup (OTLP → Tempo)
│   └── routes/
│       ├── auth.py               # /v1/auth/*  proxy
│       ├── users.py              # /v1/users/* proxy
│       ├── sessions.py           # /v1/sessions/* proxy
│       └── public.py             # /v1/public/applications/me (API key only)
│
├── services/
│   ├── auth-services/                # authentication — :8002
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic/                  # DB migrations
│   │   ├── tests/
│   │   └── app/
│   │       ├── main.py               # FastAPI app + Kafka publisher
│   │       ├── core/config.py        # pydantic-settings configuration
│   │       ├── api/routes/auth.py    # register, login, logout, refresh, verify-email, reset-password, resend-verification, deletion + email-change flows
│   │       ├── db/session.py         # async database session
│   │       ├── models/               # SQLAlchemy models (credential)
│   │       ├── repositories/         # credential repository
│   │       ├── schemas/auth.py       # request/response models
│   │       ├── security/
│   │       │   ├── hashing.py        # Argon2id hashing
│   │       │   ├── brute_force.py    # lockout counters (Redis)
│   │       │   └── verification.py   # purpose-bound HMAC one-time tokens
│   │       ├── events/
│   │       │   ├── types.py          # event contracts + topic names
│   │       │   └── publisher.py      # Kafka publisher
│   │       ├── services/auth_service.py  # orchestration logic
│   │       ├── metrics/prometheus.py
│   │       └── observability/tracing.py
│   │
│   ├── user-services/                # profiles & avatars — :8001
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic/                  # DB migrations (users, verification/reset/deletion/email-change tokens)
│   │   ├── tests/
│   │   └── app/
│   │       ├── main.py
│   │       ├── core/config.py
│   │       ├── api/routes/users.py   # public + /users/internal/* endpoints
│   │       ├── db/session.py
│   │       ├── models/               # user, verification, password_reset, deletion_request, email_change
│   │       ├── repositories/
│   │       ├── schemas/user.py
│   │       ├── services/user_service.py
│   │       ├── storage/              # avatar storage (github upload, base)
│   │       ├── metrics/prometheus.py
│   │       └── observability/tracing.py
│   │
│   ├── token-services/               # JWT lifecycle — :8003
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── tests/
│   │   └── app/
│   │       ├── main.py
│   │       ├── core/config.py
│   │       ├── api/routes/tokens.py  # generate / verify / revoke (internal only)
│   │       ├── dependencies.py       # require_internal_key
│   │       ├── cache/redis.py        # blacklist storage
│   │       ├── security/jwt.py       # JWT sign/verify (iss/aud checked)
│   │       ├── services/token_service.py
│   │       ├── schemas/token.py
│   │       └── observability/tracing.py
│   │
│   ├── session-services/             # sessions & refresh rotation — :8004
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── tests/
│   │   └── app/
│   │       ├── main.py
│   │       ├── core/config.py        # MAX_SESSIONS_PER_USER
│   │       ├── api/routes/sessions.py
│   │       ├── db/session.py
│   │       ├── models/session.py
│   │       ├── repositories/session_repo.py
│   │       ├── schemas/session.py
│   │       ├── services/session_service.py
│   │       └── observability/tracing.py
│   │
│   └── email-services/               # transactional emails — :8005
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── tests/
│       └── app/
│           ├── main.py               # wires handlers to topics
│           ├── core/config.py        # SMTP + Kafka settings
│           ├── api/routes/emails.py  # internal send endpoints
│           ├── events/
│           │   ├── subscriber.py     # Kafka consumer (EventSubscriber)
│           │   ├── handlers.py       # per-topic email handlers
│           │   └── types.py          # topic constants
│           ├── providers/smtp.py     # SMTP transport (Brevo)
│           ├── services/
│           │   ├── email_service.py
│           │   └── ip_geolocation.py # device + IP location in alerts
│           ├── templates/            # verify_email, reset_password, security_alert, new_login, account_deletion, email_change
│           └── observability/tracing.py
│
│   ├── application-services/         # application registry & API keys — :8006
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic/                  # DB migrations (applications, api_keys)
│   │   ├── tests/
│   │   └── app/
│   │       ├── main.py               # FastAPI app (internal only)
│   │       ├── core/config.py
│   │       ├── api/routes/applications.py  # /applications/* internal endpoints
│   │       ├── db/session.py
│   │       ├── models/               # Application, ApiKey (SQLAlchemy)
│   │       ├── repositories/
│   │       ├── schemas/
│   │       ├── security/key_generation.py  # key generation + SHA-256 hashing + constant-time verify
│   │       ├── cache/redis.py        # key-resolution cache (Redis DB 3)
│   │       ├── services/application_service.py
│   │       └── observability/tracing.py
│   │
├── shared/                           # shared cross-service package
│   ├── events/                       # publisher, subscribers, types
│   ├── logging/config.py
│   └── metrics/prometheus.py
│
├── tests/
│   └── e2e/
│       └── test_full_flow.py         # end-to-end tests (12 scenarios)
└── avatars/default.png               # default avatar asset
```

---

## Quick start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose

### Local development

```bash
# 1. Clone the repository
git clone https://github.com/DarcinBig/identyx-api.git
cd identyx-api

# 2. Configure the environment (dev defaults; fill the secrets)
cp .env.example .env

# 3. Start the full stack (all services + PostgreSQL, Redis, Redpanda, Prometheus)
docker compose -f infra/docker-compose.yml up -d --build
```

The gateway runs on `http://localhost:8100` — all requests go through it. Interactive
docs (Swagger UI) are available at `http://localhost:8100/docs`, Redpanda Console at
`http://localhost:8180`, Prometheus at `http://localhost:9090`, Grafana at
`http://localhost:3000` (dashboards auto-provisioned) and Tempo at
`http://localhost:3200` (traces).

Developer convenience targets are available through the root `Makefile`
(`make lint`, `make test`, `make check`, `make up`, `make down`, `make e2e`).
Pre-commit hooks (ruff) are configured in `.pre-commit-config.yaml`.

Unit tests live in `<service>/tests/unit/` (no Docker required): run them with
`uv run pytest` from a service directory, or all services with `make test`.
The E2E suite in `tests/e2e/` requires a running stack and is skipped otherwise.

> To develop a single service locally (outside Docker) instead, start the stack and
> then run the service with `uv run uvicorn app.main:app --reload --port <port>`
> from its directory — see the per-service READMEs.

### Production (Docker)

`infra/docker-compose.prod.yml` is a **standalone** production stack. Only Caddy
(ports `80`/`443`) is exposed; every service stays on the internal Docker network.
Caddy terminates HTTPS automatically with **Let's Encrypt** certificates.

Deploy on a VPS:

```bash
# 1. Point a DNS A record (e.g. api.identyx.io) at the host, then:

# 2. Prepare the production environment (fresh secrets!)
cp .env.production.example .env
#    → edit .env: DOMAIN, APP_BASE_URL, FRONTEND, CORS_ORIGINS,
#      then generate every secret with `openssl rand`:
#        openssl rand -base64 32   # POSTGRES_PASSWORD, REDIS_PASSWORD
#        openssl rand -hex 64      # JWT_SECRET_KEY
#        openssl rand -base64 48   # INTERNAL_API_KEY

# 3. Pull the pre-built images (or add `--build` to build locally)
IMAGE_TAG=V1.1.3 docker compose -f infra/docker-compose.prod.yml pull

# 4. Start the stack
IMAGE_TAG=V1.1.3 docker compose -f infra/docker-compose.prod.yml up -d

# 5. Check health
curl https://api.identyx.io/health
```

Backups (scheduled via cron):

```bash
0 2 * * * /path/to/identyx/infra/backup.sh >> /var/log/identyx-backup.log 2>&1
```

Restore (from the latest backup, or pass a specific file):

```bash
/path/to/identyx/infra/restore.sh                # latest backup in infra/backups/
/path/to/identyx/infra/restore.sh backups/db-users-2026-08-10_020001.sql.gz
```

Notes:
- Swagger/OpenAPI is **disabled** in production (`ENVIRONMENT=production`).
- Images are pulled from `ghcr.io/darcinbig/`; pin a version with `IMAGE_TAG`.
- The dev compose (`infra/docker-compose.yml`) exposes ports for local debugging
  only — never use it on a public host.

### Environment variables

The shared configuration lives in the root `.env` (loaded by every container via
`env_file`). Templates:

- `.env.example` — development defaults.
- `.env.production.example` — production template (fresh secrets required).

Key variables:

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database credentials (shared) | `identyx` / *(required)* |
| `JWT_SECRET_KEY` | HMAC secret for JWT (≥ 64 chars in prod) | *(required)* |
| `REDIS_PASSWORD` | Redis auth password | *(required)* |
| `INTERNAL_API_KEY` | Shared secret for inter-service calls (`X-Internal-Key`) | *(required)* |
| `APP_BASE_URL` | Public base URL used in email links | `http://localhost:8100` |
| `APPLICATION_SERVICE_URL` | Internal application-service URL (gateway) | `http://application-service:8006` |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,http://localhost:8000` |
| `RATE_LIMIT_REFRESH` / `RATE_LIMIT_SESSIONS` | Per-IP rate limits for refresh & sessions routes | `20` / `60` |
| `BRUTE_FORCE_MAX_ATTEMPTS` / `BRUTE_FORCE_LOCKOUT_MINUTES` | Login lockout policy (per account) | `5` / `15` |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | Grafana admin credentials | `admin` / `admin` (change in prod) |
| `OTEL_ENABLED` | Enable OpenTelemetry tracing | `true` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP/HTTP collector (Tempo) | `http://tempo:4318` |
| `TRUST_PROXY` | Read real client IP from `X-Forwarded-For` when behind a reverse proxy | `false` |
| `IDENTYX_NATIVE_TENANT_ID` | Default tenant ID for multi-tenancy isolation | `00000000-0000-0000-0000-000000000001` |

---

## API Reference

All public endpoints are versioned under `/v1`. Protected endpoints expect
`Authorization: Bearer <access_token>`. **Swagger is disabled in production** —
use the OpenAPI export in [`docs/api/APIDOG.md`](docs/api/APIDOG.md) (Apidog)
or `/docs` on a dev instance.

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/v1/auth/register` | POST | — | Create account, returns JWT pair, sends verification email |
| `/v1/auth/login` | POST | — | Login, returns JWT pair, sends new-login alert email |
| `/v1/auth/logout` | POST | JWT | Revoke session + blacklist access token |
| `/v1/auth/refresh` | POST | — | Rotate the refresh token (single-use) |
| `/v1/auth/verify-email` | GET | — | Verify email via one-time HMAC token (`?token=`) |
| `/v1/auth/reset-password` | POST | — | Set a new password with a one-time reset token |
| `/v1/auth/resend-verification` | POST | — | Re-send the verification email (anti-enumeration) |
| `/v1/auth/confirm-deletion` | POST | — | Confirm account deletion via one-time email link |
| `/v1/auth/confirm-email-change` | POST | — | Confirm the new email via one-time email link |
| `/v1/users/me` | GET | JWT | Current user profile |
| `/v1/users/{user_id}` | GET | JWT | User profile (owner only) |
| `/v1/users/{user_id}` | PATCH | JWT | Update profile (owner only) |
| `/v1/users/{user_id}` | DELETE | JWT | Delete account (email-confirmed; requires password) |
| `/v1/users/{user_id}/deletion-request` | POST | JWT | Request account deletion (requires password) |
| `/v1/users/{user_id}/email-change` | POST | JWT | Request an email change (requires password + new_email) |
| `/v1/users/{user_id}/avatar` | POST | JWT | Upload/replace avatar (`multipart/form-data`) |
| `/v1/users/{user_id}/avatar` | GET | JWT | Current avatar URL |
| `/v1/users/{user_id}/avatar` | DELETE | JWT | Remove avatar (requires password) |
| `/v1/sessions/` | GET | JWT | List active sessions |
| `/v1/sessions/revoke-all` | DELETE | JWT | Revoke all sessions |
| `/v1/sessions/{session_id}` | DELETE | JWT | Revoke a session (owner only) |
| `/v1/public/applications/me` | GET | API key | Application metadata for the presented key |
| `/health` | GET | — | Service health (incl. downstream probes) |
| `/ready` | GET | — | Readiness probe (200/503) for orchestrators |
| `/metrics` | GET | — | Prometheus scrape endpoint |

> The internal routes (`/tokens/*`, `/users/internal/*`, `/emails/*`,
> `/applications/*`) are **not** exposed through the gateway.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.14 |
| **Framework** | FastAPI, uvicorn |
| **Runtime** | Docker, Docker Compose |
| **Databases** | PostgreSQL 16 (per service), Redis 7 |
| **Auth** | JWT (HS256), Argon2id |
| **Messaging** | Kafka/Redpanda (event-driven inter-service communication) |
| **Monitoring** | Prometheus, Grafana, OpenTelemetry + Tempo, structured JSON logs |
| **CI / CD** | GitHub Actions (lint, unit tests, E2E, GHCR images), GHCR |
| **Linting** | Ruff (pre-commit hooks, Makefile targets) |

---

## Contributing

We welcome contributions! Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines on:

- Setting up a development environment
- Code style & linting
- Writing tests
- Opening issues and pull requests

---

## Roadmap

- [x] Email / password authentication
- [x] Email verification (HMAC token)
- [x] JWT access & refresh token rotation
- [x] Session management & revocation
- [x] Multi-device session limit (oldest session revoked)
- [x] New-login email alerts with device + IP geolocation
- [x] User profiles & avatar upload
- [x] GDPR account deletion (email-confirmed)
- [x] Email change with re-verification
- [x] Password confirmation on sensitive actions
- [x] Third-party application registry & API keys
- [x] Prometheus metrics + Grafana dashboards
- [x] OpenTelemetry distributed traces (Tempo)
- [x] CI pipeline with E2E suite
- [ ] OAuth 2.0 (Google, GitHub, Apple, etc.)
- [ ] Passkeys (WebAuthn)
- [ ] Multi-factor authentication (TOTP)
- [ ] Admin API & dashboard
- [ ] Audit log
- [ ] Etc.

---

## License

[MIT](LICENSE) © DarcinBig
