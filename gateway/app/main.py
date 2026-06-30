import time
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx

from app.core.logging.config import setup_logging
setup_logging(service_name="gateway")

logger = logging.getLogger("gateway")

from app.core.config import get_settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.errors import ErrorHandlingMiddleware
from app.middleware.jwt_auth import JWTAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.cors import get_cors_config
from app.metrics.prometheus import MetricsMiddleware, metrics_response
import app.http as http_state

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.sessions import router as sessions_router
from app.routes.tokens import router as tokens_router

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

_app = FastAPI(
    title="Identyx API Gateway",
    description="Single entry point for all Identyx services",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# --- CORS --------------------------------------------------
cors_config = get_cors_config()
_app.add_middleware(CORSMiddleware, **cors_config)

# --- Middlewares -------------------------------------------
_app.add_middleware(LoggingMiddleware)
_app.add_middleware(ErrorHandlingMiddleware)
_app.add_middleware(JWTAuthMiddleware)

# --- Routers -----------------------------------------------
_app.include_router(auth_router)
_app.include_router(users_router)
_app.include_router(sessions_router)
_app.include_router(tokens_router)

# --- Health check ------------------------------------------
@_app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    import asyncio

    uptime_seconds = int(time.time() - _start_time)

    services_to_check = {
        "auth-service": f"{settings.auth_service_url}/health",
        "user-service": f"{settings.user_service_url}/health",
        "token-service": f"{settings.token_service_url}/health",
        "session-service": f"{settings.session_service_url}/health",
        "email-service": f"{settings.email_service_url}/health",
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
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "services": statuses,
    }

@_app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()

# --- Pure ASGI wrapping ------------------------------------
# Execution order for incoming requests (outside → inside):
# SecurityHeaders → RateLimit → Metrics → _app (CORS, Logging, Errors, JWT, routes)
app = SecurityHeadersMiddleware(
    RateLimitMiddleware(
        MetricsMiddleware(_app, service_name="gateway")
    )
)