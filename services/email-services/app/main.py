"""email-service/app/main.py — V1.0.0"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.emails import router as emails_router
from app.core.config import get_settings
from app.core.logging.config import setup_logging
from app.events.handlers import (
    handler_auth_suspicious,
    handler_new_login,
    handler_user_deletion_requested,
    handler_user_email_change_requested,
    handler_user_registered,
)
from app.events.subscriber import EventSubscriber
from app.events.types import (
    CHANNEL_AUTH_NEW_LOGIN,
    CHANNEL_AUTH_SUSPICIOUS,
    CHANNEL_USER_DELETION_REQUESTED,
    CHANNEL_USER_EMAIL_CHANGE_REQUESTED,
    CHANNEL_USER_REGISTERED,
)
from app.metrics.prometheus import MetricsMiddleware, metrics_response
from app.observability.tracing import instrument_fastapi, setup_tracing

setup_logging(service_name="email-service")
setup_tracing(service_name="identyx-email")
logger = logging.getLogger("email-service")

settings = get_settings()
_start_time = time.time()

# Global Kafka subscriber
event_subscriber = EventSubscriber(
    bootstrap_servers=settings.kafka_bootstrap_servers,
    group_id=settings.kafka_consumer_group_id,
    client_id=settings.kafka_client_id,
)

# Register handlers
event_subscriber.on(CHANNEL_USER_REGISTERED)(handler_user_registered)
event_subscriber.on(CHANNEL_AUTH_SUSPICIOUS)(handler_auth_suspicious)
event_subscriber.on(CHANNEL_AUTH_NEW_LOGIN)(handler_new_login)
event_subscriber.on(CHANNEL_USER_DELETION_REQUESTED)(handler_user_deletion_requested)
event_subscriber.on(CHANNEL_USER_EMAIL_CHANGE_REQUESTED)(handler_user_email_change_requested)

_listener_task = None
_listener_started_at: float | None = None

_HEALTH_GRACE_SECONDS = 10.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _listener_task, _listener_started_at

    logger.info("kafka_config", extra={
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "group_id": settings.kafka_consumer_group_id,
        "topics": [
            CHANNEL_USER_REGISTERED,
            CHANNEL_AUTH_SUSPICIOUS,
            CHANNEL_AUTH_NEW_LOGIN,
            CHANNEL_USER_DELETION_REQUESTED,
            CHANNEL_USER_EMAIL_CHANGE_REQUESTED,
        ],
    })

    try:
        _listener_task = asyncio.create_task(event_subscriber.listen())
        _listener_started_at = time.time()
        logger.info("event_subscriber_started")
    except Exception as exc:
        logger.error("event_subscriber_failed", extra={"error": str(exc)})

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
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MetricsMiddleware, service_name="email-service")

app.include_router(emails_router)


# OpenTelemetry auto-instrumentation (no-op when tracing is disabled)
instrument_fastapi(app)


@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    uptime_seconds = int(time.time() - _start_time)

    subscriber_status = (
        "running"
        if _listener_task and not _listener_task.done()
        else "stopped"
    )

    # Grace period: right after startup the subscriber may still be
    # connecting to Kafka — don't report a degraded state during that window.
    if (
        subscriber_status != "running"
        and _listener_started_at is not None
        and (time.time() - _listener_started_at) < _HEALTH_GRACE_SECONDS
    ):
        subscriber_status = "starting"

    overall = "ok" if subscriber_status in ("running", "starting") else "degraded"

    return {
        "service": "email-service",
        "status": overall,
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "kafka": settings.kafka_bootstrap_servers,
            "event_subscriber": subscriber_status,
            "topics": [
                CHANNEL_USER_REGISTERED,
                CHANNEL_AUTH_SUSPICIOUS,
                CHANNEL_AUTH_NEW_LOGIN,
                CHANNEL_USER_DELETION_REQUESTED,
                CHANNEL_USER_EMAIL_CHANGE_REQUESTED,
            ],
        },
    }


@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()
