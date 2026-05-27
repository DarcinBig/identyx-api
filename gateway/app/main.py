from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
import httpx
import app.http as http_state

from app.core.config import get_settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.errors import ErrorHandlingMiddleware

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.sessions import router as sessions_router
from app.routes.tokens import router as tokens_router

settings = get_settings()
logger = logging.getLogger("gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    http_state.client= httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,        # connection timeout to a service
            read=30.0,          # response read timeout
            write=10.0,         # body writing timeout
            pool=5.0,           # pool connection timeout
        )
    )
    logger.info("[Gateway] started — listening on port 8100")
    yield
    await http_state.client.aclose()
    http_state.client = None
    logger.info("[Gateway] shutdown.")

app = FastAPI(
    title="Identyx API Gateway",
    description="Single entry point for all Identyx services",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# --- Middlewares -------------------------------------------
# The order is important: the middleware declared last
# is executed first on the incoming request.
#
# Order of execution on the request:
#   ErrorHandlingMiddleware → LoggingMiddleware → route handler
#
# Order of execution on the response:
#   route handler → LoggingMiddleware → ErrorHandlingMiddleware

app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# --- Routers -----------------------------------------------
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(sessions_router)
app.include_router(tokens_router)

# --- Health check ------------------------------------------
@app.get("/health", tags=["health"], operation_id="check")
async def health_check():
    return {
        "service": "Identyx Gateway",
        "status": "ok",
        "version": "0.1.0",
    }