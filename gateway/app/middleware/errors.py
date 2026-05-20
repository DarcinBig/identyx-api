import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("gateway.errors")

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Catches all unhandled exceptions and returns
    a structured JSON response instead of a stack trace.
    Without this middleware, an internal exception would return an
    unreadable HTML 500 response to the client.

    Error response format:
        {
            "error": "Internal server error",
            "detail": "Exception message (debug mode only)",
            "path": "/auth/login"
        }
    """
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception(
                "Unhandled exception on %s %s",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "path": str(request.url.path),
                },
            )
