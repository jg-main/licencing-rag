# api/middleware/request_id.py
"""Request ID middleware for request tracing.

Generates a unique request ID for each incoming request and includes
it in response headers for tracing and debugging.

The request ID is also stored in a context variable so that exception
handlers can access it even when the request object is not available.
"""

import uuid
from collections.abc import Awaitable
from collections.abc import Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for request ID, accessible from exception handlers
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Use this in exception handlers to include request ID in error responses.

    Returns:
        Request ID string or None if not in a request context.
    """
    return request_id_ctx.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that adds a unique request ID to each request/response.

    The request ID is:
    - Taken from incoming X-Request-ID header if present (from upstream proxy)
    - Generated as a UUID4 if no upstream request ID exists
    - Stored in request.state.request_id for access in route handlers
    - Stored in a context variable for access in exception handlers
    - Added to the response as X-Request-ID header (if not already set)

    Note: This middleware does NOT catch exceptions. Exception handlers
    should use get_request_id() to include the request ID in error responses.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and add request ID.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            Response with X-Request-ID header added.

        Raises:
            Any exception from downstream handlers is propagated unchanged
            to allow FastAPI's exception handlers to process it.
        """
        # Use existing X-Request-ID from upstream proxy, or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in request state for route handlers
        request.state.request_id = request_id

        # Store in context variable for exception handlers
        token = request_id_ctx.set(request_id)

        try:
            # Process request - exceptions propagate to FastAPI exception handlers
            response = await call_next(request)

            # Add request ID to response headers only if not already set
            if "X-Request-ID" not in response.headers:
                response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Reset context variable to prevent leaking between requests
            request_id_ctx.reset(token)
