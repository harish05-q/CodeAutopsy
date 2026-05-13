"""
Structured logging with correlation IDs.

Uses structlog for structured, JSON-capable logging.
Every log entry includes:
- timestamp
- log level
- module/function name
- correlation_id (tracks a single analysis pipeline run)
- request_id (tracks a single HTTP request)

Design decisions:
- structlog over stdlib logging for structured key-value output.
- Correlation IDs are bound per-pipeline-run, not globally.
- Console output in dev, JSON output in production.
"""

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

# Context variables for request/correlation tracking.
# These are async-safe and avoid global state.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def generate_id() -> str:
    """Generate a short unique ID for request/correlation tracking."""
    return uuid.uuid4().hex[:12]


def add_context_vars(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict,  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Inject context variables (request_id, correlation_id) into every log entry."""
    req_id = request_id_var.get("")
    corr_id = correlation_id_var.get("")
    if req_id:
        event_dict["request_id"] = req_id
    if corr_id:
        event_dict["correlation_id"] = corr_id
    return event_dict


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """
    Configure structlog and stdlib logging.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, output JSON lines. If False, colored console output.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        add_context_vars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a named, structured logger.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A bound structlog logger with the module name attached.
    """
    return structlog.get_logger(name)  # type: ignore[return-value]
