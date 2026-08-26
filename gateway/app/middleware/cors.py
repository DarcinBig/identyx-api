"""
CORS configuration for the gateway.

In development: all localhost origins are allowed.
In production: restrict to the frontend domains.

Note: we use Starlette's CORSMiddleware directly in main.py — this file contains only the configuration.
"""
from app.core.config import get_settings

settings = get_settings()

def get_cors_config() -> dict:
    """Returns the CORS configuration according to the environment"""
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