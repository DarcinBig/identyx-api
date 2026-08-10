# Session Service

Session lifecycle for Identyx. Tracks the devices logged into an account and
enforces the multi-device limit.

## Role

- **Session tracking** — each login creates a session (with device metadata);
  sessions are listed and revoked on demand.
- **Refresh-token validation** — refresh tokens are single-use: validation
  rotates the token and revokes the previous one.
- **Multi-device limit** — when the limit (`max_sessions_per_user`, default 5)
  is reached, the **oldest** session is revoked automatically.
- **Account-wide revocation** — deleting a user (or resetting a password)
  revokes all of the user's sessions through the internal routes.

Four of the five internal routes are hidden from the schema and protected by
`X-Internal-Key`.

## Tech stack

- FastAPI + uvicorn
- SQLAlchemy (async) + PostgreSQL (own database `identyx_sessions`)

## Endpoints

Public (exposed through the gateway at `/v1/sessions/*`, require JWT):

| Method | Path | Summary |
|---|---|---|
| GET | `/sessions/` | List active sessions |
| DELETE | `/sessions/revoke-all` | Revoke all sessions |
| DELETE | `/sessions/{session_id}` | Revoke a session (owner only) |

Internal (auth-service only, `include_in_schema=False`):

| Method | Path | Summary |
|---|---|---|
| POST | `/sessions/` | Create a session |
| POST | `/sessions/validate-refresh` | Validate + rotate a refresh token |
| POST | `/sessions/revoke` | Revoke a session by refresh token |
| POST | `/sessions/revoke-all` | Revoke all sessions of a user |
| POST | `/sessions/rotate` | Rotate a refresh token |

## Configuration

All variables are read from the root `.env`:

| Variable | Default | Description |
|---|---|---|
| `SESSION_SERVICE_PORT` | `8004` | Listening port |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `identyx_sessions` / `identyx` | Sessions database credentials |
| `DATABASE_URL` | `postgresql+asyncpg://...@session-db/identyx_sessions` | Overrides per-service DB config |
| `MAX_SESSIONS_PER_USER` | `5` | Multi-device limit |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8004
```

## Tests

```bash
uv run pytest
```

Unit tests cover session creation, refresh-token rotation, revocation and the
multi-device limit. End-to-end tests for the whole platform live in
[`tests/e2e`](../../tests/e2e).

## Project layout

```
app/
├── api/
│   └── routes/sessions.py  # public + internal endpoints
├── core/config.py          # pydantic-settings configuration
├── models/                 # SQLAlchemy models (session, refresh token)
├── schemas/                # Pydantic request/response models
├── services/               # session lifecycle logic
└── main.py                 # FastAPI app
```

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
