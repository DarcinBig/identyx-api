from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.db.session import Base, engine
from app.api.routes.auth import router as auth_router
from app.events.publisher import EventPublisher

settings = get_settings()

event_publisher: EventPublisher | None = None

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
    await event_publisher.connect()

    print("[Auth Service] started — tables ready, events publisher connected")
    yield

    # Close the publisher
    if event_publisher:
        await event_publisher.close()
    print("[Auth Service] shutdown.")


app = FastAPI(
    title="Identyx Auth Service",
    description="Register, login, logout, refresh",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    redirect_slashes=False,
)

app.include_router(auth_router)

@app.get("/health", tags=["health"], operation_id="check")
async def health_check():
    return {
        "service": "Identyx Auth Service",
        "status": "ok",
        "version": "0.1.0",
    }