"""
Static CORS configuration for the gateway.

The gateway resolves origins dynamically via
`DynamicCORSMiddleware` (preflight → application-service resolve-by-origin,
actual request → per-app allowed origins). The static `CORS_ORIGINS` list
remains as the environment-wide fallback and is always allowed.

This module documents that config — the + sub-set of headers the dynamic
middleware emits. It is not wired into middleware anymore.
"""
from app.core.config import get_settings

settings = get_settings()

def get_cors_config() -> dict:
    """Returns the static CORS configuration (used as a reference/fallback)"""
    origins = settings.get_cors_origins_list()

    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Identyx-Key",
        ],
        "expose_headers": [
            "X-Request-Id",
            "Retry-After",
        ],
        "max_age": 600,         # cache preflight 10 minutes
    }