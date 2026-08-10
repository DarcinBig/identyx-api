# Identyx — developer convenience targets.
#
# Every Python package (gateway + the five services) is managed independently
# by uv; these targets just fan out over them.

SERVICES := gateway services/auth-services services/user-services services/token-services services/session-services services/email-services

.PHONY: help lock sync lint lint-fix test test-e2e check up down logs e2e fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

lock: ## Refresh uv.lock for every package
	@for s in $(SERVICES); do echo "== $$s =="; (cd $$s && uv lock); done

sync: ## Install dependencies (dev) for every package
	@for s in $(SERVICES); do echo "== $$s =="; (cd $$s && uv sync --dev); done

lint: ## Ruff check on every package
	@for s in $(SERVICES); do echo "== $$s =="; (cd $$s && uv run ruff check app tests 2>/dev/null || uv run ruff check app); done
	@echo "== root =="
	@uv run ruff check . --exclude 'gateway/uv.lock'

lint-fix: ## Auto-fix Ruff violations on every package
	@for s in $(SERVICES); do echo "== $$s =="; (cd $$s && uv run ruff check --fix app tests 2>/dev/null || uv run ruff check --fix app); done

test: ## Run unit/integration tests for every package that has any
	@for s in $(SERVICES); do if ls $$s/tests/*.py >/dev/null 2>&1; then echo "== $$s =="; (cd $$s && uv run pytest -q); fi; done
	@echo "== root =="
	@uv run pytest -q

test-e2e: ## Run the E2E pytest suite against a running stack (infra/docker-compose.yml)
	@uv run pytest tests/e2e -v

check: lint test ## Lint + test everything

fmt: ## Format (isort + fix) every package
	@for s in $(SERVICES); do echo "== $$s =="; (cd $$s && uv run ruff check --fix app tests 2>/dev/null || uv run ruff check --fix app); done

up: ## Build and start the full development stack
	docker compose -f infra/docker-compose.yml up -d --build

down: ## Stop the full stack (keep volumes)
	docker compose -f infra/docker-compose.yml down

e2e: ## Start the stack then run the E2E suite, then tear down
	cp .env.example .env
	sed -i 's/^RATE_LIMIT_REGISTER=.*/RATE_LIMIT_REGISTER=100/' .env
	docker compose -f infra/docker-compose.yml up -d --build
	uv run pytest tests/e2e -v
	docker compose -f infra/docker-compose.yml down -v

logs: ## Tail logs of the full stack
	docker compose -f infra/docker-compose.yml logs -f --tail=100
