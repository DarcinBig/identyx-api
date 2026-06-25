from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx
import logging

from app.core.config import get_settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.errors import ErrorHandlingMiddleware
from app.middleware.jwt_auth import JWTAuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.cors import get_cors_config
import app.http as http_state

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
    logger.info("[Gateway] started — listening on port %s", settings.gateway_port)
    yield
    if http_state.client:
        await http_state.client.aclose()
        http_state.client = None
    logger.info("[Gateway] shutdown.")

_app = FastAPI(
    title="Identyx API Gateway",
    description="Single entry point for all Identyx services",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# --- CORS --------------------------------------------------

cors_config = get_cors_config()
_app.add_middleware(CORSMiddleware, **cors_config)

# --- Middlewares -------------------------------------------
# BaseHTTPMiddleware middlewares (logging, errors, JWT)
# add_middleware order: last added = first executed

_app.add_middleware(LoggingMiddleware)
_app.add_middleware(ErrorHandlingMiddleware)
_app.add_middleware(JWTAuthMiddleware)

# Pure ASGI middlewares — manual wrapping
# Wraps the FastAPI app directly
# _app.middleware_stack = None     # reset to force rebuild

# --- Routers -----------------------------------------------

_app.include_router(auth_router)
_app.include_router(users_router)
_app.include_router(sessions_router)
_app.include_router(tokens_router)

# --- Health check ------------------------------------------
@_app.get("/health", tags=["health"], operation_id="check")
async def health_check():
    return {
        "service": "Identyx Gateway",
        "status": "ok",
        "version": "0.1.0",
    }

# Pure ASGI wrapper after app construction
# This wraps the entire app, including all FastAPI middlewares
# _original_build = app.build_middleware_stack
#
# def _build_with_asgi_middlewares():
#     stack = _original_build()
#     stack = RateLimitMiddleware(stack)
#     stack = SecurityHeadersMiddleware(stack)
#     return stack
#
# app.build_middleware = _build_with_asgi_middlewares

# Pure ASGI wrapping AFTER the app is fully built
# SecurityHeaders wraps everything — executed first on the request
# RateLimit sits below SecurityHeaders but before the rest
app = SecurityHeadersMiddleware(RateLimitMiddleware(_app))