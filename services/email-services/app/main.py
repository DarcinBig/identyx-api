"""email-service/app/main.py — V0.1.5"""

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
    handler_user_registered,
)
from app.events.subscriber import EventSubscriber
from app.events.types import (
    CHANNEL_AUTH_NEW_LOGIN,
    CHANNEL_AUTH_SUSPICIOUS,
    CHANNEL_USER_REGISTERED,
)
from app.metrics.prometheus import MetricsMiddleware, metrics_response

setup_logging(service_name="email-service")
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

_listener_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _listener_task

    logger.info("kafka_config", extra={
        "bootstrap_servers": settings.kafka_bootstrap_servers,
        "group_id": settings.kafka_consumer_group_id,
        "topics": [
            CHANNEL_USER_REGISTERED,
            CHANNEL_AUTH_SUSPICIOUS,
            CHANNEL_AUTH_NEW_LOGIN,
        ],
    })

    try:
        _listener_task = asyncio.create_task(event_subscriber.listen())
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
    version="0.1.5",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MetricsMiddleware, service_name="email-service")

app.include_router(emails_router)


@app.get("/health", tags=["observability"], operation_id="check")
async def health_check():
    uptime_seconds = int(time.time() - _start_time)

    subscriber_status = (
        "running"
        if _listener_task and not _listener_task.done()
        else "stopped"
    )

    return {
        "service": "email-service",
        "status": "ok" if subscriber_status == "running" else "degraded",
        "version": "0.1.5",
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "kafka": settings.kafka_bootstrap_servers,
            "event_subscriber": subscriber_status,
            "topics": [
                CHANNEL_USER_REGISTERED,
                CHANNEL_AUTH_SUSPICIOUS,
                CHANNEL_AUTH_NEW_LOGIN,
            ],
        },
    }


@app.get("/metrics", tags=["observability"], operation_id="metrics", include_in_schema=False)
async def metrics():
    return metrics_response()
