# Application Service

Third-party applications registry and API key resolution for Identyx.
Port **:8006**. Source of truth for applications and their API keys
(`pk_live_...` / `sk_live_...`, Stripe-aligned format).

Called only by internal services — it has **no public routes** and is not yet
proxied by the gateway. The gateway config and both compose files already carry
`APPLICATION_SERVICE_URL` (`http://application-service:8006`), ready for the
`/v1/applications/*` proxy routes (staged for the next release). Every API key is
resolved through the internal `POST /applications/verify-key`.

## Role

- **Create** — creates an application (1 app = 1 tenant) and issues its first
  publishable + secret key pair. The full keys are returned **exactly once**.
- **Verify** — resolves an API key into `{tenant_id, application_id, key_type,
  allowed_origins, status}`. Cache-first (Redis DB 3), DB on miss, cache on
  success. This is the hot path used by the gateway on every request.
- **Rotate** — issues a fresh key pair while keeping the old ones active
  (no-downtime rotation).
- **Revoke** — soft-revokes a key and **actively invalidates the cache**
  (no 60s TTL wait).
- **Introspect** — `GET /applications/me` returns non-sensitive application
  metadata for the key presented in `X-Identyx-Key`.

All routes are protected by `X-Internal-Key` (`require_internal_key`) and
hidden from the OpenAPI schema (`include_in_schema=False`).

## Key security model

- `key_id` (DB) — prefix + first 8 chars of the random part. Indexed, **not
  secret**, used for fast lookups and dashboard identification.
- `key_hash` (DB) — SHA-256 of the full secret string.
- The full key (prefix + 24 base62 chars ≈ 142 bits) is never stored in plain
  text and only ever shown once, at creation or rotation.
- SHA-256 + `hmac.compare_digest` (constant-time) — not Argon2id: API keys are
  verified on every request under load.

## Tech stack

- FastAPI + uvicorn
- SQLAlchemy (async) + Alembic — own database `postgres-applications`
- Redis DB 3 — key resolution cache (TTL 60s, active invalidation on revoke)

## Endpoints

Internal only (never exposed directly):

| Method | Path | Summary |
|---|---|---|
| POST | `/applications` | Create an application + first key pair (admin / break-glass) |
| POST | `/applications/verify-key` | Resolve a key into a tenant (gateway hot path) |
| GET | `/applications/me` | Non-sensitive app metadata for the presented key |
| POST | `/applications/{id}/keys` | Rotate keys (new pair, old ones stay active) |
| DELETE | `/applications/{id}/keys/{key_id}` | Revoke a key (immediate cache invalidation) |
| GET | `/applications/{id}` | Read an application (admin) |
| PATCH | `/applications/{id}` | Update name / allowed_origins / webhook_url / status |

## Configuration

All variables are read from the root `.env` (via the service's own
`.env.example`):

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host (`postgres-applications` in Docker) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | — | PostgreSQL credentials |
| `POSTGRES_DB` | `identyx_applications` | Own database |
| `REDIS_URL` | — | Full Redis URL; falls back to `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` |
| `REDIS_DB` | `3` | Dedicated DB for the key resolution cache |
| `API_KEY_CACHE_TTL_SECONDS` | `60` | Cache TTL (safety net only) |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build application-service
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8006
```

Migrations are applied automatically at startup (Alembic). To run them
manually:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1   # verify reversibility
```

## Tests

```bash
uv run pytest
```

Unit tests (61) cover key generation/hashing/verification, the application and API
key repositories, cache round-trips, cache invalidation and cache-hit secret
re-validation (regression). End-to-end tests for the whole platform live in
[`tests/e2e`](../../tests/e2e).

## Project layout

```
app/
├── api/routes/applications.py   # all /applications/* endpoints (internal only)
├── core/config.py               # pydantic-settings configuration
├── dependencies.py              # require_internal_key
├── db/session.py                # async engine + session
├── models/                      # Application + ApiKey (SQLAlchemy)
├── repositories/                # SQL access (application_repo, api_key_repo)
├── schemas/                     # Pydantic request/response models
├── security/key_generation.py   # key generation, SHA-256 hashing, constant-time verify
├── cache/redis.py               # resolution cache (Redis DB 3, active invalidation)
├── services/application_service.py  # orchestration
└── main.py                      # FastAPI app
```

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
