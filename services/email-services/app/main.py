import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.api.routes.emails import router as emails_router
from app.events.subscriber import EventSubscriber
from app.events.types import CHANNEL_USER_REGISTERED
from app.events.handlers import handler_user_registered

settings = get_settings()

# Global subscriber
event_subscriber = EventSubscriber(
    redis_url=settings.get_events_redis_url()
)

# Register handlers
event_subscriber.on(CHANNEL_USER_REGISTERED)(handler_user_registered)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the subscriber in the background
    listener_track = asyncio.create_task(event_subscriber.listen())
    print("[Email Service] started — event subscriber running")
    yield

    # Stop
    listener_track.cancel()
    try:
        await listener_track
    except asyncio.CancelledError:
        pass
    print("[Email Service] shutdown.")

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