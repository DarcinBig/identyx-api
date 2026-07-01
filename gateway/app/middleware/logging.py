import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Structured logger for the gateway
logger = logging.getLogger("gateway")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs each HTTP request:

    - method (GET, POST, etc.)
    - path (/auth/login)
    - status code of the response
    - processing time in milliseconds

    Example log:
        2026-04-28 12:00:00 | INFO | gateway | POST /auth/login 200 42ms
    """
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "%s %s %s %sms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
