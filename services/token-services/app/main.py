from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Token Session] starting...")
    yield
    print("[Token Session] shutdown.")

app = FastAPI(
    title="Identyx Token Service",
    description="JWT generation and validation",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "service": "Identyx Token Service",
        "status": "ok",
        "version": "0.1.0",
    }