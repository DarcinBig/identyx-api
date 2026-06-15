from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.api.routes.emails import router as emails_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Email Service] started")
    yield
    print("[Email Service] shutdown.")

app = FastAPI(
    title="Identyx Email Service",
    description="Email sending",
    version="0.0.1",
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