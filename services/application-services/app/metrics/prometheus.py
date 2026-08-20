"""
Prometheus metrics for application-service.

Metrics exposed via the `GET /metrics` endpoint:

  http_requests_total{service, method, path, status}
    → Counter for the total number of HTTP requests

  http_request_duration_seconds{service, method, path}
    → Histogram of request duration

  active_requests{service}
    → Gauge for the number of active requests
"""

import time

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# --- Metrics ------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["service", "method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    "active_requests",
    "Number of active HTTP requests",
    ["service"],
)

# --- Middleware ---------------------------------------------------


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Prometheus middleware — records every HTTP request.
    Does not count `/metrics` itself, to avoid recursion.
    """

    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Do not instrument /metrics
        if path == "/metrics":
            return await call_next(request)

        method = request.method
        ACTIVE_REQUESTS.labels(service=self.service_name).inc()
        start = time.time()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.time() - start
            ACTIVE_REQUESTS.labels(service=self.service_name).dec()

            HTTP_REQUESTS_TOTAL.labels(
                service=self.service_name,
                method=method,
                path=path,
                status=status,
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                service=self.service_name,
                method=method,
                path=path,
            ).observe(duration)

        return response


# --- Endpoint /metrics --------------------------------------------


def metrics_response() -> Response:
    """
    Returns Prometheus metrics in text/plain format.
    To be hooked up to GET /metrics in each service.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
