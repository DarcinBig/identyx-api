import asyncio
import logging
import time
from contextlib import asynccontextmanager

from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from app.api.routes.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.db.session import engine
from app.metrics.prometheus import MetricsMiddleware, metrics_response
from app.observability.tracing import instrument_fastapi, setup_tracing

setup_logging(service_name="session-service")

setup_tracing(service_name="identyx-session")

logger = logging.getLogger("session-service")

settings = get_settings()

_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)

    def _run_alembic_upgrade() -> None:
        from sqlalchemy import create_engine, text

        alembic_cfg = Config("alembic.ini")
        sync_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://")
        sync_engine = create_engine(sync_url)

        with sync_engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(71276345)"))
            try:
                has_version = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = 'alembic_version'"
                    )
                ).fetchone() is not None

                has_tables = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name != 'alembic_version' LIMIT 1"
                    )
                ).fetchone() is not None

                if has_tables and not has_version:
                    command.stamp(alembic_cfg, "head")
                    logger.info("alembic_stamped_existing_db")
                    return

                command.upgrade(alembic_cfg, "head")
                logger.info("alembic_migrations_applied")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(71276345)"))

        sync_engine.dispose()

    await asyncio.to_thread(_run_alembic_upgrade)

    logger.info("service_started")
    yield
    logger.info("service_stopped")

app = FastAPI(
    title="Identyx Session Service",
    description="Session and refresh tokens",
    version="1.1.2",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MetricsMiddleware, service_name="session-service")

app.include_router(sessions_router)

# OpenTelemetry auto-instrumentation (no-op when tracing is disabled)
instrument_fastapi(app)

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
        "version": "1.1.2",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "database": db_status,
        }
    }

@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()