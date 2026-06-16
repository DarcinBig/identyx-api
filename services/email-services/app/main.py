import asyncio
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.api.routes.emails import router as emails_router
from app.events.subscriber import EventSubscriber
from app.events.types import CHANNEL_USER_REGISTERED
from app.events.handlers import handler_user_registered

settings = get_settings()
logger = logging.getLogger("uvicorn.error")

# Global subscriber
event_subscriber = EventSubscriber(
    redis_url=settings.get_events_redis_url()
)

# Register handlers
logger.info(f"[DEBUG] Redis events URL: {settings.get_events_redis_url()}")
event_subscriber.on(CHANNEL_USER_REGISTERED)(handler_user_registered)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the subscriber in the background
    try:
        listener_track = asyncio.create_task(event_subscriber.listen())
        logger.info("[Email Service] started ? event subscriber running")
    except Exception as exc:
        # print("[Email Service] started — event subscriber running")
        logger.info(f"[Email Service] failed to start subscriber: {exc}")
    yield

    # Stop
    listener_track.cancel()
    try:
        await listener_track
    except asyncio.CancelledError:
        pass
    logger.info("[Email Service] shutdown.")

app = FastAPI(
    title="Identyx Email Service",
    description="Transactional email sending",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.include_router(emails_router)

@app.get("/health", tags=["health"], operation_id="check")
async def health_check():
    return {
        "service": "Identyx Email Service",
        "status": "ok",
        "version": "0.1.0",
    }