# Gateway

Single entry point of the Identyx platform. All client traffic goes through the
gateway; internal services are never reachable directly from outside.

## Role

- **Reverse proxy** — routes `/v1/auth/*`, `/v1/users/*`, `/v1/sessions/*` to the
  corresponding internal services.
- **JWT validation** — verifies the access token before forwarding, then injects
  the `X-User-Id` header used downstream.
- **Rate limiting** — Redis-backed, per-IP limits on global traffic and on
  sensitive routes (login, register, password reset, email verification).
- **Operational endpoints** — `/health` (with downstream probes) and `/metrics`
  (Prometheus).
- **Docs** — Swagger UI at `/docs` and `/openapi.json`, **disabled when
  `ENVIRONMENT=production`**. The OpenAPI export lives in
  [`docs/api/openapi.json`](../docs/api/openapi.json).

## Tech stack

- FastAPI + uvicorn
- httpx (service proxying)
- Redis (rate limiting, `DB 2`)
- prometheus-client (metrics)

## Exposed endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `/v1/auth/*` | mixed | Registration, login, logout, refresh, email verification, password reset |
| `/v1/users/*` | JWT | Profile & avatar management |
| `/v1/sessions/*` | JWT | Session listing and revocation |
| `/health` | — | Liveness + readiness of downstream services |
| `/metrics` | — | Prometheus metrics |
| `/docs`, `/openapi.json` | — | Swagger UI + OpenAPI spec (dev only) |

The gateway never exposes the internal routes of the services
(`/tokens/*`, `/users/internal/*`, …).

## Configuration

All variables are read from the root `.env` (see
[`.env.example`](../.env.example)):

| Variable | Default | Description |
|---|---|---|
| `GATEWAY_PORT` | `8100` | Listening port |
| `ENVIRONMENT` | `development` | `production` disables `/docs` |
| `APP_BASE_URL` | `http://localhost:8100` | Public base URL (OpenAPI `servers`) |
| `USER_SERVICE_URL` | `http://user-service:8001` | Internal user-service URL |
| `AUTH_SERVICE_URL` | `http://auth-service:8002` | Internal auth-service URL |
| `TOKEN_SERVICE_URL` | `http://token-service:8003` | Internal token-service URL |
| `SESSION_SERVICE_URL` | `http://session-service:8004` | Internal session-service URL |
| `EMAIL_SERVICE_URL` | `http://email-service:8005` | Internal email-service URL |
| `JWT_SECRET_KEY` | — | Secret used to validate JWTs (HS256) |
| `RATE_LIMIT_GLOBAL` | `100` | Global requests/minute per IP |
| `RATE_LIMIT_LOGIN` | `10` | Login requests/minute per IP |
| `RATE_LIMIT_REGISTER` | `5` | Register requests/minute per IP |
| `RATE_LIMIT_RESET_PASSWORD` | `3` | Password reset requests/minute per IP |
| `RATE_LIMIT_VERIFY_EMAIL` | `5` | Email verification requests/minute per IP |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000` | Allowed origins (comma-separated) |

## Running locally

The full stack is started from the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run only the gateway against a running stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8100
```

Gateway is then reachable at `http://localhost:8100` (docs at `/docs`).

## Tests

```bash
uv run pytest
```

The gateway unit tests cover JWT validation, rate-limit guards and proxy wiring.
End-to-end tests for the whole platform live in [`tests/e2e`](../tests/e2e).

## Project layout

```
app/
├── main.py          # FastAPI app, routers, /health, /metrics
├── core/
│   └── config.py    # pydantic-settings configuration
├── routes/
│   ├── auth.py      # /v1/auth/* proxy
│   ├── users.py     # /v1/users/* proxy
│   └── sessions.py  # /v1/sessions/* proxy
├── middleware/      # rate limiting, CORS
└── services/        # httpx clients to internal services
```

Full API documentation: [`docs/api/APIDOG.md`](../docs/api/APIDOG.md).
