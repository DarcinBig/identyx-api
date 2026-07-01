import time
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
from fastapi import Request, Response


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


class MetricsMiddleware:
    """
    Pure ASGI middleware — consistent with RateLimitMiddleware
    and SecurityHeadersMiddleware from the gateway.
    """

    def __init__(self, app, service_name: str = "gateway"):
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        ACTIVE_REQUESTS.labels(service=self.service_name).inc()
        start = time.time()
        status_holder = {"status": "500"}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = str(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start
            ACTIVE_REQUESTS.labels(service=self.service_name).dec()

            HTTP_REQUESTS_TOTAL.labels(
                service=self.service_name,
                method=method,
                path=path,
                status=status_holder["status"],
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                service=self.service_name,
                method=method,
                path=path,
            ).observe(duration)


def metrics_response() -> Response:
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )