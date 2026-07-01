import time
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.logging.config import setup_logging
setup_logging(service_name="session-service")

logger = logging.getLogger("session-service")

from app.core.config import get_settings
from app.db.session import Base, engine
from app.api.routes.sessions import router as sessions_router
from app.metrics.prometheus import MetricsMiddleware, metrics_response

settings = get_settings()

_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("service_started")
    yield
    logger.info("service_stopped")

app = FastAPI(
    title="Identyx Session Service",
    description="Session and refresh tokens",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MetricsMiddleware, service_name="session-service")

app.include_router(sessions_router)

@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    from sqlalchemy import text

    uptime_seconds = int(time.time() - _start_time)

    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        logger.error("health_check_failed", extra={"error": str(exc)})

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "service": "session-service",
        "status": overall,
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "database": db_status,
        }
    }

@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()