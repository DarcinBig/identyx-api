# <picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.png"><source media="(prefers-color-scheme: light)" srcset="docs/images/logo-light.png"><img alt="Identyx" src="docs/images/logo-light.png" width="32"></picture> Identyx

> Authentication & Identity API — *v0.1.5*

[![CI](https://github.com/DarcinBig/identyx-api/actions/workflows/ci.yml/badge.svg)](https://github.com/DarcinBig/identyx-api/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.14-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-059487?logo=fastapi)](https://fastapi.tiangolo.com)

<!--
  Add your architecture diagram / banner image here:
  ![Identyx Architecture](docs/images/architecture.png)
  Supported formats: PNG, SVG. Recommended width: 800–1200px.
  Place images in docs/images/.
-->

**Identyx** is a production-ready authentication and identity platform built with **FastAPI** and a microservices architecture. Designed for security, scalability, and seamless integration across web and mobile applications.

### Vision

| Feature | Status |
|---|---|
| **Email / Password auth** | ✅ Done |
| **JWT access + refresh tokens** | ✅ Done |
| **Session management** | ✅ Done |
| **User profile management** | ✅ Done |
| **Email notifications** | ✅ Done |
| **Prometheus metrics & structured logging** | ✅ Done |
| **OAuth 2.0 providers (Google, GitHub, …)** | 🔜 Planned |
| **Passkeys (WebAuthn)** | 🔜 Planned |
| **Multi-factor authentication (MFA / TOTP)** | 🔜 Planned |

---

## Architecture

<!--
  Architecture diagram placeholder:
  ![Architecture Diagram](docs/images/architecture.png)
  Shows the gateway proxying to auth, user, token, session, email services,
  backed by PostgreSQL (per service), Redis, and Prometheus.
-->

Identyx follows an **API Gateway** pattern with **6 microservices**, each owning its data store:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Auth    │     │  User    │     │  Token   │     │ Session  │     │  Email   │
│ Service  │     │ Service  │     │ Service  │     │ Service  │     │ Service  │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     ▼                ▼                ▼                ▼                ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│PostgreSQL│     │PostgreSQL│     │  Redis   │     │PostgreSQL│     │ Redpanda │
│ (auth)   │     │ (users)  │     │(brute-   │     │(sessions)│     │ (events) │
│          │     │          │     │ force)   │     │          │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                                    ┌──────────┐
                                                                    │   SMTP   │
                                                                    │(Mailpit) │
                                                                    └──────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                               Gateway                                      │
│  Rate limiting · JWT validation · Routing · Prometheus metrics · CORS     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                              Clients
                        (Web / Mobile / CLI)
```

### Services overview

| Service | Role | Tech |
|---|---|---|
| **gateway** | Single entry point; rate limits, JWT validation, routing | FastAPI + Redis |
| **auth-service** | Register / login, password hashing (Argon2id), brute-force protection | FastAPI + PostgreSQL + Redis |
| **user-service** | CRUD user profiles, avatar upload | FastAPI + PostgreSQL |
| **token-service** | JWT generation, verification, blacklisting | FastAPI + Redis |
| **session-service** | Session lifecycle & validation | FastAPI + PostgreSQL |
| **email-service** | Transactional emails via Kafka/Redpanda event stream | FastAPI + Kafka + SMTP |

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

# 2. Start infrastructure (PostgreSQL, Redis, Redpanda, Prometheus)
docker compose -f infra/docker-compose.yml up -d

# 3. Run a service (example: auth-service)
cd services/auth-services
uv sync
uv run uvicorn app.main:app --reload --port 8002
```

The gateway runs on `http://localhost:8100` — all requests go through it.

### Production (Docker)

```bash
docker compose -f infra/docker-compose.yml \
              -f infra/docker-compose.prod.yml \
              up -d
```

Images are pulled from `ghcr.io/darcinbig/`. Pin a version with `IMAGE_TAG=v0.1.5`.

### Environment variables

Each service has a `.env` file at its root. Key variables:

| Variable | Description | Default |
|---|---|---|
| `postgres_user` / `postgres_password` | Database credentials | *(required)* |
| `jwt_secret_key` | HMAC secret for JWT | *(required)* |
| `redis_url` | Redis connection string | `redis://localhost:6379` |

See `infra/.env.example` for the full list.

---

## API Reference

The gateway exposes:

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/auth/register` | POST | — | Create account |
| `/auth/login` | POST | — | Login, returns JWT pair |
| `/users/me` | GET | JWT | Current user profile |
| `/users/me` | PATCH | JWT | Update profile |
| `/sessions` | GET | JWT | List active sessions |
| `/sessions/{id}` | DELETE | JWT | Revoke session |
| `/tokens/refresh` | POST | — | Rotate refresh token |
| `/tokens/revoke` | POST | JWT | Blacklist token |
| `/health` | GET | — | Service health (incl. downstream probes) |
| `/metrics` | GET | — | Prometheus scrape endpoint |

Full interactive docs at [`/docs`](http://localhost:8100/docs) (Swagger UI) or [`/redoc`](http://localhost:8100/redoc) (ReDoc).

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
| **Monitoring** | Prometheus, structured JSON logs |
| **CI / CD** | GitHub Actions, GHCR |
| **Linting** | Ruff |

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
- [x] JWT access & refresh token rotation
- [x] Session management & revocation
- [x] User profiles & avatar upload
- [ ] OAuth 2.0 (Google, GitHub, Apple, etc.)
- [ ] Passkeys (WebAuthn)
- [ ] Multi-factor authentication (TOTP)
- [ ] Admin API & dashboard
- [ ] Audit log
- [ ] Etc.

---

## License

[MIT](LICENSE) © DarcinBig
