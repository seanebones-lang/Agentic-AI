"""Middleware for authentication, rate limiting, and request logging."""

import time
from typing import Callable, Optional

from fastapi import Header, HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from observability.logger import get_logger, set_correlation_id

logger = get_logger(__name__)
settings = get_settings()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or set_correlation_id()

        start_time = time.time()

        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id,
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration,
                correlation_id=correlation_id,
            )

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_seconds=duration,
                correlation_id=correlation_id,
            )

            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    def __init__(self, app: any):
        """Initialize rate limit middleware."""
        super().__init__(app)
        self.request_counts: dict[str, list[float]] = {}
        self.window_seconds = 60
        self.max_requests = settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit and process request."""
        # Get client identifier (IP address or API key)
        client_id = request.client.host if request.client else "unknown"
        api_key = request.headers.get(settings.api_key_header)
        if api_key:
            client_id = api_key

        current_time = time.time()

        # Initialize or clean up old requests
        if client_id not in self.request_counts:
            self.request_counts[client_id] = []

        # Remove requests outside the time window
        self.request_counts[client_id] = [
            req_time
            for req_time in self.request_counts[client_id]
            if current_time - req_time < self.window_seconds
        ]

        # Check rate limit
        if len(self.request_counts[client_id]) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                request_count=len(self.request_counts[client_id]),
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per minute.",
            )

        # Add current request
        self.request_counts[client_id].append(current_time)

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            self.max_requests - len(self.request_counts[client_id])
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(current_time + self.window_seconds)
        )

        return response


async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias=settings.api_key_header)
) -> str:
    """
    Validate API key from request headers.

    Args:
        x_api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # In development, allow requests without API key
    if settings.is_development and not x_api_key:
        logger.warning("API key not provided (development mode)")
        return "dev-key"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # In production, validate against stored API keys
    # This is a placeholder - implement proper key validation
    # For example, check against database or environment variable
    valid_keys = ["demo-api-key", "test-api-key"]  # Replace with proper validation

    if settings.is_production and x_api_key not in valid_keys:
        logger.warning("Invalid API key attempted", api_key_prefix=x_api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return x_api_key

