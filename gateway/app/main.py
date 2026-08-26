import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

import app.http as http_state
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.metrics.prometheus import MetricsMiddleware, metrics_response
from app.middleware.api_key_auth import ApiKeyAuthMiddleware
from app.middleware.cors import get_cors_config
from app.middleware.errors import ErrorHandlingMiddleware
from app.middleware.jwt_auth import JWTAuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware, get_rate_limit_redis
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.observability.tracing import instrument_fastapi, setup_tracing
from app.routes.auth import router as auth_router
from app.routes.public import router as public_router
from app.routes.sessions import router as sessions_router
from app.routes.users import router as users_router

setup_logging(service_name="gateway")

setup_tracing(service_name="identyx-gateway")

logger = logging.getLogger("gateway")

settings = get_settings()

_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    http_state.client= httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,        # connection timeout to a service
            read=30.0,          # response read timeout
            write=10.0,         # body writing timeout
            pool=5.0,           # pool connection timeout
        )
    )
    logger.info("service_started", extra={"port": settings.gateway_port})
    yield
    if http_state.client:
        await http_state.client.aclose()
        http_state.client = None
    logger.info("service_stopped")

_is_production = settings.environment == "production"

_openapi_tags = [
    {
        "name": "auth",
        "description": "Registration, authentication, token refresh, email verification and password reset.",
    },
    {
        "name": "users",
        "description": "User profile management and avatar upload. Every route requires a valid JWT.",
    },
    {
        "name": "sessions",
        "description": "Active session management (list, revoke). Every route requires a valid JWT.",
    },
    {
        "name": "public",
        "description": "Public API key introspection. Authenticated via X-Identyx-Key header (no JWT).",
    },
    {
        "name": "observability",
        "description": "Operational endpoints (health, Prometheus metrics).",
    },
]

_app = FastAPI(
    title="Identyx API Gateway",
    description=(
        "Single entry point for all Identyx services.\n\n"
        "All endpoints are versioned under `/v1`. Protected endpoints expect an "
        "`Authorization: Bearer <access_token>` header. Access tokens are issued by "
        "`POST /v1/auth/login` (or `/v1/auth/register`) and rotated by `POST /v1/auth/refresh`."
    ),
    version="1.1.2",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
    servers=[{"url": settings.app_base_url, "description": "Identyx API"}],
    openapi_tags=_openapi_tags,
    redirect_slashes=False,
)

# --- CORS --------------------------------------------------

cors_config = get_cors_config()
_app.add_middleware(CORSMiddleware, **cors_config)

# --- Middlewares -------------------------------------------

_app.add_middleware(LoggingMiddleware)
_app.add_middleware(ErrorHandlingMiddleware)
_app.add_middleware(JWTAuthMiddleware)
_app.add_middleware(ApiKeyAuthMiddleware)

# --- Routers -----------------------------------------------
# The public API is versioned under /v1.
# Each router proxies to the internal services (unversioned).

_api_version = "/v1"

_app.include_router(auth_router, prefix=_api_version)
_app.include_router(users_router, prefix=_api_version)
_app.include_router(sessions_router, prefix=_api_version)
_app.include_router(public_router, prefix=_api_version)

# OpenTelemetry auto-instrumentation (no-op when tracing is disabled)
instrument_fastapi(_app)

# --- Health check ------------------------------------------

@_app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    """
    Liveness probe for the gateway and its downstream services.

    Public route — no JWT required. Used by load balancers, orchestrators
    and the Docker healthchecks.

    **Success** `200` — `{service, status, version, uptime_seconds, services}`.
    Each downstream service reports `ok`, `http_<code>` or `error: <type>`.
    `status` is `ok` only when every service reports `ok`, otherwise `degraded`.
    """
    import asyncio

    uptime_seconds = int(time.time() - _start_time)

    services_to_check = {
        "auth-service": f"{settings.auth_service_url}/health",
        "user-service": f"{settings.user_service_url}/health",
        "token-service": f"{settings.token_service_url}/health",
        "session-service": f"{settings.session_service_url}/health",
        "email-service": f"{settings.email_service_url}/health",
        "application-service": f"{settings.application_service_url}/health",
    }

    statuses = {}

    async def check_service(name: str, url: str):
        try:
            if http_state.client:
                response = await http_state.client.get(url, timeout=3.0)
                statuses[name] = "ok" if response.status_code == 200 else f"http_{response.status_code}"
            else:
                statuses[name] = "client_not_ready"
        except Exception as exc:
            statuses[name] = f"error: {type(exc).__name__}"

    await asyncio.gather(
        *[check_service(name, url) for name, url in services_to_check.items()]
    )

    overall = "ok" if all(value == "ok" for value in statuses.values()) else "degraded"

    return {
        "service": "gateway",
        "status": overall,
        "version": "1.1.2",
        "uptime_seconds": uptime_seconds,
        "services": statuses,
    }

@_app.get("/ready", tags=["observability"], operation_id="ready", responses={200: {}, 503: {}})
async def ready_check(response: Response):
    """
    Readiness probe for the gateway.

    Returns `200` when the gateway can proxy traffic (HTTP client up, rate-limit
    Redis reachable, all downstream services healthy). Returns `503` otherwise.

    Public route — no JWT required. Used by orchestrators before routing
    traffic to the gateway.
    """
    import asyncio

    from fastapi import status

    uptime_seconds = int(time.time() - _start_time)

    dependencies: dict[str, str] = {}

    if http_state.client is None:
        dependencies["http_client"] = "not_ready"
    else:
        dependencies["http_client"] = "ok"

    try:
        redis = await get_rate_limit_redis()
        await redis.ping()
        dependencies["redis"] = "ok"
    except Exception as exc:
        dependencies["redis"] = f"error: {type(exc).__name__}"

    services_to_check = {
        "auth-service": f"{settings.auth_service_url}/health",
        "user-service": f"{settings.user_service_url}/health",
        "token-service": f"{settings.token_service_url}/health",
        "session-service": f"{settings.session_service_url}/health",
        "email-service": f"{settings.email_service_url}/health",
        "application-service": f"{settings.application_service_url}/health",
    }

    service_statuses = {}

    async def check_service(name: str, url: str):
        try:
            if http_state.client:
                resp = await http_state.client.get(url, timeout=3.0)
                service_statuses[name] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
            else:
                service_statuses[name] = "client_not_ready"
        except Exception as exc:
            service_statuses[name] = f"error: {type(exc).__name__}"

    await asyncio.gather(
        *[check_service(name, url) for name, url in services_to_check.items()]
    )

    ready = (
        dependencies["http_client"] == "ok"
        and dependencies["redis"] == "ok"
        and all(value == "ok" for value in service_statuses.values())
    )

    body = {
        "service": "gateway",
        "ready": ready,
        "version": "1.1.2",
        "uptime_seconds": uptime_seconds,
        "dependencies": dependencies,
        "services": service_statuses,
    }

    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return body

@_app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()

# --- Pure ASGI wrapping ------------------------------------
# Execution order for incoming requests (outside → inside):
# SecurityHeaders → RateLimit → Metrics →
#   _app (ApiKeyAuth → JWTAuth → Errors → Logging → CORS → routes)
#
# Key invariant: ApiKeyAuthMiddleware must wrap JWTAuthMiddleware
# (added AFTER it) so it executes first and can set
# scope["api_key_authenticated"] for API-key-only routes.
app = SecurityHeadersMiddleware(
    RateLimitMiddleware(
        MetricsMiddleware(_app, service_name="gateway")
    )
)