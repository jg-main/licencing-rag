# api/middleware/logging.py
"""Request logging middleware for observability.

Logs incoming requests and outgoing responses with timing information.
Requires RequestIDMiddleware to be registered first for request ID tracing.
"""

import time
import traceback
from collections.abc import Awaitable
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.config import TRUST_PROXY_HEADERS
from app.logging import get_logger

log = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Uses X-Forwarded-For header only when TRUST_PROXY_HEADERS is enabled.
    This prevents IP spoofing when the app is exposed directly.

    Args:
        request: The incoming HTTP request.

    Returns:
        Client IP address string.
    """
    # Only trust proxy headers when explicitly configured (behind ALB/nginx)
    if TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For format: "client, proxy1, proxy2"
            # First IP is the original client
            return forwarded_for.split(",")[0].strip()

    # Fall back to direct connection IP
    return request.client.host if request.client else "unknown"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request/response information.

    Logs:
    - Request start: method, path, client IP, user agent
    - Request end: status code, latency in ms
    - Request ID (from RequestIDMiddleware)
    - Errors: exception details with request context

    Middleware Order:
        In FastAPI/Starlette, middleware is executed in REVERSE registration order.
        For request_id to be available in logs, register middleware like this:

            app.add_middleware(RequestLoggingMiddleware)  # Runs second
            app.add_middleware(RequestIDMiddleware)       # Runs first

        This ensures RequestIDMiddleware sets request.state.request_id
        BEFORE RequestLoggingMiddleware tries to read it.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and log timing information.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response from the handler.
        """
        start_time = time.time()

        # Get request ID if set by RequestIDMiddleware
        request_id = getattr(request.state, "request_id", None)

        # Get client IP (respects TRUST_PROXY_HEADERS setting)
        client_ip = _get_client_ip(request)

        # Get user agent for logging
        user_agent = request.headers.get("User-Agent", "unknown")

        # Get auth type placeholder (will be set by auth middleware in Phase 4)
        auth_type = getattr(request.state, "auth_type", None)

        # Log request start
        log.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            user_agent=user_agent[:100] if user_agent else None,  # Truncate long UAs
            auth_type=auth_type,
            request_id=request_id,
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log request end
            log.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                request_id=request_id,
            )

            return response

        except Exception as e:
            # Calculate latency even for errors
            latency_ms = int((time.time() - start_time) * 1000)

            # Log error with request context
            log.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                client_ip=client_ip,
                latency_ms=latency_ms,
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=traceback.format_exc(),
            )

            # Re-raise to let FastAPI's exception handlers deal with it
            raise
