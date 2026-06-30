import time
import asyncio
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.logging.config import setup_logging
setup_logging(service_name="email-service")

logger = logging.getLogger("email-service")

from app.core.config import get_settings
from app.api.routes.emails import router as emails_router
from app.events.subscriber import EventSubscriber
from app.events.types import CHANNEL_USER_REGISTERED
from app.events.handlers import handler_user_registered
from app.metrics.prometheus import MetricsMiddleware, metrics_response

settings = get_settings()

_start_time = time.time()

# Global subscriber
event_subscriber = EventSubscriber(
    redis_url=settings.get_events_redis_url()
)

# Register handlers
logger.info("redis_events_url_configured", extra={"redis_url": settings.get_events_redis_url()[:30]})
event_subscriber.on(CHANNEL_USER_REGISTERED)(handler_user_registered)

_listener_track = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _listener_task

    try:
        _listener_task = asyncio.create_task(event_subscriber.listen())
        logger.info("event_subscriber_started")
    except Exception as exc:
        logger.error("event_subscriber_failed_to_start", extra={"error": str(exc)})

    logger.info("service_started")
    yield

    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
    logger.info("service_stopped")

app = FastAPI(
    title="Identyx Email Service",
    description="Transactional email sending",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MetricsMiddleware, service_name="email-service")

app.include_router(emails_router)

@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    import redis.asyncio as aioredis

    uptime_seconds = int(time.time() - _start_time)

    redis_status = "ok"
    try:
        client = aioredis.from_url(settings.get_events_redis_url())
        await client.ping()
        await client.aclose()
    except Exception as exc:
        redis_status = f"error: {exc}"
        logger.error("health_check_redis_failed", extra={"error": str(exc)})

    subscriber_status = "running" if _listener_task and not _listener_task.done() else "stopped"

    overall = "ok" if redis_status == "ok" else "degraded"

    return {
        "service": "email-service",
        "status": overall,
        "version": "0.1.0",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "redis_events": redis_status,
            "event_subscriber": subscriber_status,
        },
    }

@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()