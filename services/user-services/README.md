# User Service

User profile management for Identyx. Owns the users database and serves both the
public profile routes and the internal endpoints used by the auth-service.

## Role

- **Profile CRUD** — create, read, update, delete user profiles; ownership is
  enforced (`X-User-Id` from the gateway must match the target `user_id`).
- **Avatar management** — upload (JPEG/PNG/WebP, max 5 MB), fetch and reset;
  avatars are served from raw public URLs.
- **Email verification** — stores and clears the HMAC verification token issued
  by the auth-service.
- **One-time token storage** — SHA-256 hashes of purpose-bound tokens for
  verification, password reset, account deletion and email change
  (`deletion_request`, `email_change` tables; `pending_email` column).
- **Internal endpoints** — `GET /users/internal/by-email`,
  `GET /users/internal/by-id`, verification/reset/deletion/email-change token
  endpoints, consumed by the auth-service, protected by `X-Internal-Key` and
  **hidden from the schema**.

## Tech stack

- FastAPI + uvicorn
- SQLAlchemy (async) + PostgreSQL (own database `identyx_users`)
- Multipart file uploads (python-multipart)

## Endpoints

Public (exposed through the gateway at `/v1/users/*`, all require JWT):

| Method | Path | Summary |
|---|---|---|
| GET | `/users/me` | Current user profile (`X-User-Id` header) |
| GET | `/users/{user_id}` | User profile (owner only) |
| PATCH | `/users/{user_id}` | Update profile (owner only) |
| DELETE | `/users/{user_id}` | Delete account + revoke sessions (owner only) |
| POST | `/users/{user_id}/deletion-request` | Store a deletion-request token |
| POST | `/users/{user_id}/email-change` | Store an email-change token + `pending_email` |
| POST | `/users/{user_id}/avatar` | Upload/replace avatar |
| GET | `/users/{user_id}/avatar` | Current avatar URL |
| DELETE | `/users/{user_id}/avatar` | Reset avatar to default |

Internal (auth-service only, `include_in_schema=False`):

| Method | Path | Summary |
|---|---|---|
| POST | `/users/` | Create a new user |
| GET | `/users/internal/by-email` | Get user by email (login) |
| GET | `/users/internal/by-id` | Get user by ID (refresh, logout) |
| POST | `/users/internal/verification-token` | Store the email verification token |
| POST | `/users/internal/deletion-request-token` | Store the deletion token |
| POST | `/users/internal/check-deletion-token` | Validate a deletion token |
| POST | `/users/internal/confirm-deletion` | Mark the token used + delete the profile |
| POST | `/users/internal/email-change-token` | Store the email-change token + `pending_email` |
| POST | `/users/internal/check-email-change-token` | Validate an email-change token |
| POST | `/users/internal/confirm-email-change` | Mark the token used + apply the new email |

## Configuration

All variables are read from the root `.env`:

| Variable | Default | Description |
|---|---|---|
| `USER_SERVICE_PORT` | `8001` | Listening port |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `identyx_users` / `identyx` | Users database credentials |
| `DATABASE_URL` | `postgresql+asyncpg://...@user-db/identyx_users` | Overrides per-service DB config |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8001
```

## Tests

```bash
uv run pytest
```

End-to-end tests for the whole platform live in
[`tests/e2e`](../../tests/e2e).

## Project layout

```
app/
├── api/
│   └── routes/users.py   # public + internal endpoints
├── core/config.py        # pydantic-settings configuration
├── models/               # user, verification, password_reset, deletion_request, email_change
├── schemas/              # Pydantic request/response models
├── services/             # profile, avatar & one-time-token logic
├── metrics/prometheus.py # Prometheus metrics
├── observability/        # OpenTelemetry setup
└── main.py               # FastAPI app
```

Database schema is managed with Alembic (`alembic/versions/0001` … `0005`:
users → verifications → password resets → deletion requests → email changes).

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
