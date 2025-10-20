"""Structured logging with correlation IDs and CloudWatch integration."""

import logging
import sys
from contextvars import ContextVar
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog
from structlog.types import FilteringBoundLogger

from config import get_settings

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def setup_logging() -> None:
    """Configure structured logging based on settings."""
    settings = get_settings()

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
    ]

    # Add appropriate renderer based on format
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )


def get_logger(name: str) -> FilteringBoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracing."""
    if correlation_id is None:
        correlation_id = str(uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


class LoggerMixin:
    """Mixin to add logging capabilities to classes."""

    @property
    def logger(self) -> FilteringBoundLogger:
        """Get logger instance for this class."""
        return get_logger(self.__class__.__name__)

