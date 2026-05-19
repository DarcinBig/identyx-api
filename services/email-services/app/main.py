from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Email Service] starting...")
    yield
    print("[Email Service] shutdown.")

app = FastAPI(
    title="Identyx Email Service",
    description="Email sending",
    version="0.0.1",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "service": "Identyx Email Service",
        "status": "ok",
        "version": "0.1.0",
    }