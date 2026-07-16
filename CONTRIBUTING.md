# Contributing to Identyx

Thank you for your interest in contributing! This document outlines the process for reporting issues, submitting changes, and maintaining code quality.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

---

## Code of Conduct

This project adheres to the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

---

## Getting Started

1. Fork the repository.
2. Clone your fork:
   ```bash
   git clone https://github.com/DarcinBig/identyx-api.git
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/DarcinBig/identyx-api.git
   ```
4. Create a branch from `dev`:
   ```bash
   git checkout dev
   git checkout -b feat/my-feature
   ```

---

## Development Setup

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker & Docker Compose

### Local environment

```bash
# Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# Work on a specific service
cd services/auth-services
uv sync --dev
```

### Environment variables

Each service reads a `.env` file from its root. Copy the example and fill in values:

```bash
cp infra/.env.example services/auth-services/.env
```

Key variables that must be set:
- `postgres_user` / `postgres_password`
- `jwt_secret_key`

---

## Coding Standards

### Python

- **Target version**: Python 3.14
- **Formatter / linter**: [Ruff](https://docs.astral.sh/ruff/)
- **Rules enabled**: `E`, `F`, `I`, `UP`
- **Line length**: 100

Run linting before committing:

```bash
cd services/auth-services
uv run ruff check .
```

### Naming conventions

| Element | Convention | Example |
|---|---|---|
| Files / directories | `snake_case` | `session_repo.py` |
| Classes | `PascalCase` | `SessionRepository` |
| Functions / methods | `snake_case` | `validate_session()` |
| Variables | `snake_case` | `refresh_token` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_LOGIN_ATTEMPTS` |

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short description>

<optional body>
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`.

---

## Testing

All services use **pytest** with `asyncio` mode.

```bash
cd services/auth-services
uv run pytest tests/ -v --tb=short
```

- Unit tests go in `tests/unit/`
- Integration tests go in `tests/integration/`
- New features must include tests
- No test should depend on external infrastructure (mock DB / Redis)

---

## Pull Request Process

1. Ensure your branch is up to date with `dev`:
   ```bash
   git fetch upstream
   git rebase upstream/dev
   ```
2. Run linting and tests for the services you changed:
   ```bash
   cd services/auth-services
   uv run ruff check .
   uv run pytest tests/
   ```
3. Push your branch and open a PR against `dev`:
   ```bash
   git push origin feat/my-feature
   ```
4. In the PR description, include:
   - What the change does
   - Why it's needed
   - How it was tested (manual / automated)
5. Maintainers will review and may request changes.

### PR checklist

- [ ] Code follows Ruff linting rules
- [ ] Tests pass
- [ ] New tests added for new functionality
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow Conventional Commits

---

## Issue Reporting

- **Bug reports**: Include steps to reproduce, expected vs actual behavior, and relevant logs.
- **Feature requests**: Describe the use case and proposed solution.

Use the provided GitHub issue templates when available.

---

## Project structure

```
identyx-api/
├── gateway/                  # API Gateway
│   ├── app/
│   │   ├── core/             # Config, logging
│   │   ├── middleware/       # JWT, rate-limit, CORS, security
│   │   ├── routes/           # Proxy routes
│   │   └── metrics/          # Prometheus
│   └── tests/
├── services/
│   ├── auth-services/        # Auth logic
│   ├── user-services/        # User profiles
│   ├── token-services/       # JWT lifecycle
│   ├── session-services/     # Session management
│   └── email-services/       # Email notifications
├── infra/                    # Docker Compose, .env
├── docs/                     # Images, diagrams
└── .github/workflows/        # CI pipeline
```

---

*Thank you for helping make Identyx better!*
