# Auth Service

Core authentication service of Identyx. Handles account creation, login, logout,
token refresh, email verification, password reset, GDPR account deletion and
email change.

## Role

- **Register / login** — creates accounts, validates credentials against the
  auth database, returns the JWT pair issued by the token-service.
- **Password hashing** — Argon2id via `argon2-cffi`.
- **Brute-force protection** — Redis-backed (DB 2): 5 failed attempts lock the
  account for 15 minutes; each lockout publishes an `auth.suspicious` event.
- **Email verification** — issues and validates one-time **HMAC** tokens
  (opaque to the client) for `/verify-email`.
- **Password reset** — validates the one-time reset token, updates the password
  and revokes the user's sessions.
- **Account deletion (GDPR)** — confirms the password, issues a purpose-bound
  `delete_account` token and only deletes the credential + revokes every session
  after the email-confirmation link is validated.
- **Email change** — stores the new address as `pending_email` on the user-service
  and applies it only after a purpose-bound `email_change` token is confirmed.
- **Purpose-bound tokens** — every one-time token embeds its `purpose`
  (`email_verification | password_reset | delete_account | email_change`) in the
  HMAC signature, so a token cannot be replayed across flows.
- **Events** — publishes lifecycle events to Redpanda/Kafka:
  `user.registered`, `auth.login`, `auth.new_login`, `auth.suspicious`,
  `user.deletion_requested`, `user.email_change_requested`.
- **Inter-service calls** — uses the user-service internal endpoints
  (`GET /users/internal/by-email`, `POST /users/internal/verification-token`,
  …) protected by `X-Internal-Key`.

## Tech stack

- FastAPI + uvicorn
- SQLAlchemy (async) + PostgreSQL (own database `identyx_auth`)
- Redis (brute-force counters, DB 2)
- JWT via the token-service (generation/verification)
- aiokafka (event publishing to Redpanda)

## Endpoints

| Method | Path | Auth | Summary |
|---|---|---|---|
| POST | `/auth/register` | — | Register a new user (returns JWT pair, sends verification email) |
| POST | `/auth/login` | — | Login (returns JWT pair, publishes new-login event) |
| POST | `/auth/logout` | JWT | Logout (revokes session, blacklists the access token) |
| POST | `/auth/refresh` | — | Rotate the refresh token (single-use) |
| GET | `/auth/verify-email?token=...` | — | Verify the email with a one-time HMAC token |
| POST | `/auth/reset-password` | — | Set a new password with a one-time reset token |
| POST | `/auth/resend-verification` | — | Re-send the verification email (anti-enumeration) |
| POST | `/auth/internal/deletion-request` | Internal | Store a deletion-request token (gateway → auth-service) |
| POST | `/auth/confirm-deletion` | — | Confirm account deletion via one-time email link |
| POST | `/auth/internal/email-change` | Internal | Store an email-change token (gateway → auth-service) |
| POST | `/auth/confirm-email-change` | — | Confirm the new email via one-time email link |

These routes are exposed to clients **only** through the gateway at `/v1/auth/*`.

## Configuration

All variables are read from the root `.env`:

| Variable | Default | Description |
|---|---|---|
| `AUTH_SERVICE_PORT` | `8002` | Listening port |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `identyx_auth` / `identyx` | Auth database credentials |
| `DATABASE_URL` | `postgresql+asyncpg://...@auth-db/identyx_auth` | Overrides per-service DB config |
| `REDIS_URL` | `redis://redis:6379` | Redis base URL |
| `BRUTE_FORCE_MAX_ATTEMPTS` | `5` | Failed attempts before lockout |
| `BRUTE_FORCE_LOCKOUT_MINUTES` | `15` | Lockout duration |
| `KAFKA_BOOTSTRAP_SERVERS` | `redpanda:9092` | Event broker |
| `ACCESS_TOKEN_EXPIRES_MINUTES` | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRES_DAYS` | `7` | Refresh token TTL |
| `USER_SERVICE_URL` | `http://user-service:8001` | user-service internal URL |
| `TOKEN_SERVICE_URL` | `http://token-service:8003` | token-service internal URL |
| `SESSION_SERVICE_URL` | `http://session-service:8004` | session-service internal URL |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Events

Published to Redpanda (topic names in `app/events/types.py`):

| Topic | Emitted on |
|---|---|
| `user.registered` | Successful registration (email-service sends the verification email) |
| `auth.login` | Successful login |
| `auth.new_login` | Login from a new device/location (email-service sends an alert) |
| `auth.suspicious` | Brute-force lockout |
| `user.deletion_requested` | Account deletion requested (email-service sends the confirmation link) |
| `user.email_change_requested` | Email change requested (email-service sends the confirmation link) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8002
```

## Tests

```bash
uv run pytest
```

Unit tests cover registration, login, logout, refresh, email verification,
password reset, the brute-force guard, account deletion and email change
(including purpose-bound token validation). End-to-end tests for the whole
platform live in [`tests/e2e`](../../tests/e2e).

## Observability

Prometheus metrics on `/metrics` and OpenTelemetry tracing (OTLP → Tempo) — see
`app/observability/tracing.py`. Tracing is a no-op unless `OTEL_ENABLED` and
`OTEL_EXPORTER_OTLP_ENDPOINT` are set.

## Project layout

```
app/
├── api/
│   └── routes/auth.py    # public + internal endpoints
├── core/config.py        # pydantic-settings configuration
├── events/               # Kafka publishing (publisher, types)
├── models/               # SQLAlchemy models (user, credentials)
├── schemas/              # Pydantic request/response models
├── security/             # Argon2id, brute-force guard, purpose-bound HMAC tokens
├── services/             # auth logic
├── metrics/prometheus.py # Prometheus metrics
├── observability/        # OpenTelemetry setup
└── main.py               # FastAPI app
```

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
