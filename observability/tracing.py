"""LangSmith integration for LLM call tracing and execution flow visualization."""

import os
from functools import wraps
from typing import Any, Callable, Dict, Optional

from config import get_settings
from observability.logger import get_logger

logger = get_logger(__name__)


def setup_tracing() -> None:
    """Configure LangSmith tracing if enabled."""
    settings = get_settings()

    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        logger.info("LangSmith tracing enabled", project=settings.langsmith_project)
    else:
        logger.info("LangSmith tracing disabled (no API key provided)")


def trace_agent_execution(
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable:
    """Decorator to trace agent execution with LangSmith."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Async wrapper for tracing."""
            trace_name = name or func.__name__
            trace_metadata = metadata or {}

            logger.info(
                "Starting traced execution",
                function=trace_name,
                metadata=trace_metadata,
            )

            try:
                result = await func(*args, **kwargs)
                logger.info("Traced execution completed", function=trace_name)
                return result
            except Exception as e:
                logger.error(
                    "Traced execution failed",
                    function=trace_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Sync wrapper for tracing."""
            trace_name = name or func.__name__
            trace_metadata = metadata or {}

            logger.info(
                "Starting traced execution",
                function=trace_name,
                metadata=trace_metadata,
            )

            try:
                result = func(*args, **kwargs)
                logger.info("Traced execution completed", function=trace_name)
                return result
            except Exception as e:
                logger.error(
                    "Traced execution failed",
                    function=trace_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class TracingContext:
    """Context manager for tracing execution blocks."""

    def __init__(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Initialize tracing context."""
        self.name = name
        self.metadata = metadata or {}

    def __enter__(self) -> "TracingContext":
        """Enter tracing context."""
        logger.info("Entering traced context", context=self.name, metadata=self.metadata)
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Exit tracing context."""
        if exc_type:
            logger.error(
                "Traced context failed",
                context=self.name,
                error=str(exc_val),
                error_type=exc_type.__name__,
            )
        else:
            logger.info("Exiting traced context", context=self.name)

