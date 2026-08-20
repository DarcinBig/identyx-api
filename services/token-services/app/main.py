import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.tokens import router as tokens_router
from app.cache.redis import close_redis, get_redis, init_redis
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.metrics.prometheus import MetricsMiddleware, metrics_response
from app.observability.tracing import instrument_fastapi, setup_tracing

setup_logging(service_name="token-service")

setup_tracing(service_name="identyx-token")

logger = logging.getLogger("token-service")

settings = get_settings()

_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_redis()
        client = await get_redis()
        await client.ping()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_connection_failed", extra={"error": str(exc)})

    logger.info("service_started")
    yield

    await close_redis()
    logger.info("service_stopped")

app = FastAPI(
    title="Identyx Token Service",
    description="JWT generation and validation",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    redirect_slashes=False,
)

app.add_middleware(MetricsMiddleware, service_name="token-service")

app.include_router(tokens_router)

# OpenTelemetry auto-instrumentation (no-op when tracing is disabled)
instrument_fastapi(app)

@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    uptime_seconds = int(time.time() - _start_time)

    redis_status = "ok"
    try:
        client = await get_redis()
        await client.ping()
    except Exception as exc:
        redis_status = f"error: {exc}"
        logger.info("health_check_failed", extra={"error": str(exc)})

    overall = "ok" if redis_status == "ok" else "degraded"

    return {
        "service": "token-service",
        "status": overall,
        "version": "1.1.0",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "redis":  redis_status,
        }
    }

@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()