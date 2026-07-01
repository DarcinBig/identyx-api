"""
JSON structured logging configuration.

All logs are emitted in JSON format to stdout for
collection by Docker or a log aggregator (Loki, ELK in future versions).

Format of each log line:
{
    "timestamp": "2026-06-15T10:00:00.000Z",
    "level": "INFO",
    "service": "auth-service",
    "logger": "app.services.auth_service",
    "message": "User registered successfully",
    "request_id": "uuid-xxx",   ← if available
    "user_id": "uuid-yyy",      ← if available
    "duration_ms": 42.3         ← if available
}
"""
import logging
import sys
from pythonjsonlogger.json import JsonFormatter

def setup_logging(service_name: str, level: str = "INFO") -> None:
    """
    Configures structured JSON logging for the service.
    Call this at startup in main.py before any other code.

    Args:
        service_name : name of the service (e.g., "auth-service")
        level        : log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Format JSON with standard fields
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
            "message": "message",
        }
    )

    # Handler stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Add the service name to each LogRecord
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service =service_name
        return record

    logging.setLogRecordFactory(record_factory)

    # Reduce noise from third-party libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)