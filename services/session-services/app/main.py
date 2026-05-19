from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Session Service] starting...")
    yield
    print("[Session Service] shutdown.")

app = FastAPI(
    title="Identyx Session Service",
    description="Session and refresh tokens",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "service": "Identyx Session Service",
        "status": "ok",
        "version": "0.1.0",
    }