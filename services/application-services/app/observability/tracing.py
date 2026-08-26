"""
OpenTelemetry tracing setup.

Tracing is enabled only when a collector is reachable, i.e. when
`OTEL_EXPORTER_OTLP_ENDPOINT` is set or `OTEL_ENABLED=true`. Otherwise the
OpenTelemetry no-op default provider is kept, adding zero overhead.

Usage in `main.py`:
    from app.observability.tracing import instrument_fastapi, setup_tracing

    setup_tracing(service_name="identyx-applications", version="1.1.2")
    instrument_fastapi(app)
"""

import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_SERVICE_VERSION = "1.1.2"

_OTEL_ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_ENDPOINT"
_OTEL_ENABLED_ENV = "OTEL_ENABLED"


def _tracing_enabled() -> bool:
    if os.getenv(_OTEL_ENABLED_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return bool(os.getenv(_OTEL_ENDPOINT_ENV, "").strip())


def setup_tracing(service_name: str, version: str = _DEFAULT_SERVICE_VERSION) -> bool:
    """
    Install the OTLP tracer provider.

    Returns True when a real provider was configured, False when the
    no-op default is kept (local runs, tests).
    """
    if not _tracing_enabled():
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": version,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    logger.info("opentelemetry_enabled")
    return True


def instrument_fastapi(app) -> None:
    """
    Auto-instrument FastAPI routes and outgoing HTTP calls.

    A no-op when tracing is disabled. Must be called after the app instance
    (and its routers) has been built.
    """
    if not _tracing_enabled():
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    logger.info("opentelemetry_instrumentation_attached")
