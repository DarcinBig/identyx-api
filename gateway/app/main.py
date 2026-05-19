from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx

from app.core.config import get_settings

settings = get_settings()

# HTTP client shared between all requests
# Initialized at startup, closed at shutdown
http_client: httpx.AsyncClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=30.0)
    print("[Gateway] starting...")
    yield
    await http_client.aclose()
    print("[Gateway] shutdown.")

app = FastAPI(
    title="Identyx API Gateway",
    description="Single entry point for all Identyx services",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "service": "Identyx Gateway",
        "status": "ok",
        "version": "0.1.0",
    }