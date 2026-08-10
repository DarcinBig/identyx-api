# Token Service

JWT lifecycle for Identyx: generation, verification and blacklisting.
Called only by other internal services — it has **no public routes**.

## Role

- **Generate** — issues the access/refresh token pair for a user and session.
- **Verify** — validates an access token (signature, expiry, blacklist) and
  returns the claims; used by the gateway before forwarding a request.
- **Revoke** — blacklists an access token in Redis (used by logout).

All three routes are protected by `X-Internal-Key` (`require_internal_key`) and
hidden from the OpenAPI schema (`include_in_schema=False`).

## Tech stack

- FastAPI + uvicorn
- PyJWT (HS256)
- Redis (access-token blacklist, DB 0)

## Endpoints

Internal only (never exposed through the gateway):

| Method | Path | Summary |
|---|---|---|
| POST | `/tokens/generate` | Generate an access/refresh token pair for a user + session |
| GET | `/tokens/verify` | Verify an access token, return claims |
| POST | `/tokens/revoke` | Blacklist an access token until its natural expiry |

The gateway validates every incoming JWT through `/tokens/verify` before routing.

## Configuration

All variables are read from the root `.env`:

| Variable | Default | Description |
|---|---|---|
| `TOKEN_SERVICE_PORT` | `8003` | Listening port |
| `JWT_SECRET_KEY` | — | HMAC secret used to sign and verify JWTs |
| `JWT_ALGORITHM` | `HS256` | Signature algorithm |
| `REDIS_URL` | `redis://:...@redis:6379/0` | Redis URL (blacklist storage) |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8003
```

## Tests

```bash
uv run pytest
```

Unit tests cover token generation, verification and revocation. End-to-end
tests for the whole platform live in [`tests/e2e`](../../tests/e2e).

## Project layout

```
app/
├── api/
│   └── routes/tokens.py   # generate / verify / revoke (internal only)
├── core/config.py         # pydantic-settings configuration
├── dependencies.py        # require_internal_key
├── schemas/               # Pydantic request/response models
├── services/
│   └── token_service.py   # JWT sign, verify, blacklist logic
└── main.py                # FastAPI app
```

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
