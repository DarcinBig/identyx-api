import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.db.session import engine
from app.events.publisher import EventPublisher
from app.metrics.prometheus import MetricsMiddleware, metrics_response

setup_logging(service_name="auth-service")

logger = logging.getLogger("auth-service")

settings = get_settings()

_start_time = time.time()

event_publisher: EventPublisher | None = None


def _run_alembic_upgrade() -> None:
    from alembic.config import Config

    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_publisher

    # Alembic migrations on startup
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("alembic_migrations_applied")
    except Exception as exc:
        logger.error("alembic_migrations_failed", extra={"error": str(exc)})
        raise

    # Kafka publisher
    event_publisher = EventPublisher(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        client_id=settings.kafka_client_id,
    )
    try:
        await event_publisher.connect()
        logger.info("kafka_publisher_ready")
    except Exception as exc:
        logger.warning("kafka_publisher_failed", extra={"error": str(exc)})
        event_publisher = None

    logger.info("service_started")
    yield

    if event_publisher:
        await event_publisher.close()

    await engine.dispose()
    logger.info("service_stopped")


app = FastAPI(
    title="Identyx Auth Service",
    version="0.1.5",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Prometheus metrics
app.add_middleware(MetricsMiddleware, service_name="auth-service")

app.include_router(auth_router)

@app.get("/health", tags=["observability"])
async def health_check():
    from sqlalchemy import text

    uptime_seconds = int(time.time() - _start_time)

    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        logger.error("health_check_db_failed", extra={"error": str(exc)})

    kafka_status = "ok" if event_publisher and event_publisher._producer else "disabled"

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "service": "auth-service",
        "status": overall,
        "version": "0.1.5",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "database": db_status,
            "kafka": kafka_status,
        },
    }


@app.get("/metrics", tags=["observability"], include_in_schema=False)
async def metrics():
    return metrics_response()