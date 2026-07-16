import asyncio
import logging
import time
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.db.session import engine
from app.metrics.prometheus import MetricsMiddleware, metrics_response

setup_logging(service_name="user-service")

logger = logging.getLogger("user-service")

settings = get_settings()

_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates tables at startup if they don't exist
    # In production → replaced by Alembic
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    def _run_alembic_upgrade() -> None:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_alembic_upgrade)
    logger.info("alembic_migrations_applied")

    logger.info("service_started")
    yield
    logger.info("service_stopped")

app = FastAPI(
    title="Identyx User Service",
    description="User profiles and management",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    redirect_slashes=False,
)

app.add_middleware(MetricsMiddleware, service_name="user-service")

app.include_router(users_router)

@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    from sqlalchemy import text

    uptime_seconds = int(time.time() - _start_time)

    db_status = "ok"
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        logger.error("health_check_failed", extra={"error": str(exc)})

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "service": "user-service",
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