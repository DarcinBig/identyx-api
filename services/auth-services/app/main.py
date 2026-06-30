import time
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

# --- JSON logging — MUST be configured first -------------------------------------

from app.core.logging.config import setup_logging
setup_logging(service_name="auth-service")

logger = logging.getLogger("auth-service")

from app.core.config import get_settings
from app.db.session import Base, engine
from app.api.routes.auth import router as auth_router
from app.events.publisher import EventPublisher
from app.metrics.prometheus import MetricsMiddleware, metrics_response

settings = get_settings()

# Global publisher
event_publisher: EventPublisher | None = None

# Start timestamp for uptime calculation
_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_publisher

    # Creates the user_credentials table if it doesn't exist
    # In production → will be replaced by Alembic
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Publisher events
    event_publisher = EventPublisher(
        redis_url=settings.get_events_redis_url()
    )
    try:
        await event_publisher.connect()
        logger.info("events_publisher_connected", extra={"redis_url": settings.get_events_redis_url()[:20]})
    except Exception as exc:
        logger.warning("events_punlisher_failed", extra={"error": str(exc)})
        event_publisher = None
    logger.info("service_started")
    yield

    # Close the publisher
    if event_publisher:
        await event_publisher.close()
logger.info("service_stopped")


app = FastAPI(
    title="Identyx Auth Service",
    description="Register, login, logout, refresh",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    redirect_slashes=False,
)

# Prometheus metrics
app.add_middleware(MetricsMiddleware, service_name="auth-service")

app.include_router(auth_router)

@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    """
    Enhanced health check.
    Verifies the actual status of each dependency.
    """
    import asyncio
    from sqlalchemy import text

    uptime_seconds = int(time.time() - _start_time)

    # Check the database
    db_status = "ok"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"
        logger.error("health_check_db_failed", extra={"error": str(exc)})

    # Check Redis (events)
    redis_status = "ok" if event_publisher and event_publisher._client else "disabled"
    if event_publisher and event_publisher._client:
        try:
            await event_publisher._client.ping()
        except Exception as exc:
            redis_status = f"error: {exc}"

    overall = "ok" if db_status == "ok" else "degraded"

    return {
        "service": "auth-service",
        "status": overall,
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "database": db_status,
            "redis_events": redis_status,
        },
    }

# --- /metrics prometheus ---------------------------------------------------------

@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrics — scraped by Prometheus every 15s."""
    return metrics_response()