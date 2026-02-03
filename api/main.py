# api/main.py
"""FastAPI application entry point for the License Intelligence API.

This module initializes the FastAPI application with:
- Request ID middleware for tracing
- Request logging middleware for observability
- CORS middleware configuration
- Global exception handlers for consistent error responses
- Health, query, and sources route registration

Usage:
    uvicorn api.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import API_VERSION
from api.config import RAG_CORS_ORIGINS
from api.exceptions import APIError
from api.middleware import RequestIDMiddleware
from api.middleware import RequestLoggingMiddleware
from api.middleware import get_request_id
from api.routes import health_router
from api.routes import query_router
from api.routes import slack_router
from api.routes import sources_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="License Intelligence API",
    description=(
        "REST API for querying market data license agreements using "
        "Retrieval-Augmented Generation (RAG). Provides programmatic access "
        "to licensing document analysis and Slack integration."
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# =============================================================================
# Exception Handlers
# =============================================================================


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    """Build a consistent error response with request ID.

    Args:
        status_code: HTTP status code.
        code: Error code (e.g., 'VALIDATION_ERROR').
        message: Human-readable error message.
        details: Optional additional error context.

    Returns:
        JSONResponse with X-Request-ID header and consistent body format.
    """
    request_id = get_request_id()

    error_info: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if details:
        error_info["details"] = details

    content: dict[str, object] = {
        "success": False,
        "error": error_info,
    }

    # Only include request_id when present for schema cleanliness
    if request_id:
        content["request_id"] = request_id

    response = JSONResponse(status_code=status_code, content=content)

    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom APIError exceptions with consistent format.

    Converts APIError to ErrorResponse format and includes request ID.
    Adds rate limit headers for RateLimitError.
    """
    from api.exceptions import RateLimitError

    response = _build_error_response(
        exc.status_code, exc.code, exc.message, exc.details
    )

    # Add rate limit headers for RateLimitError
    if isinstance(exc, RateLimitError):
        # Get headers from request state if available
        rate_limit_headers = getattr(request.state, "rate_limit_headers", None)
        if rate_limit_headers:
            for header_name, header_value in rate_limit_headers.items():
                response.headers[header_name] = header_value

    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle HTTPException with consistent error format.

    Converts HTTPException to ErrorResponse format and includes request ID.
    Handles both string and dict detail formats.
    """
    # Extract error info from exception detail
    if isinstance(exc.detail, dict):
        # Structured detail (e.g., {"code": "SOURCE_NOT_FOUND", "message": "..."})
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", str(exc.detail))
        details = exc.detail.get("details")
    else:
        # Simple string detail
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail) if exc.detail else "An error occurred"
        details = None

    return _build_error_response(exc.status_code, code, message, details)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with consistent error format.

    Converts Pydantic validation errors to ErrorResponse format.
    """
    errors = exc.errors()

    # Build a summary message
    if len(errors) == 1:
        err = errors[0]
        field = ".".join(str(loc) for loc in err.get("loc", []))
        message = f"Validation error in {field}: {err.get('msg', 'invalid value')}"
    else:
        message = f"{len(errors)} validation errors"

    # Include detailed error info
    details = {
        "errors": [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "reason": err.get("msg"),
                "type": err.get("type"),
            }
            for err in errors
        ]
    }

    return _build_error_response(400, "VALIDATION_ERROR", message, details)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with consistent error format.

    Logs the exception and returns a generic 500 error.
    """
    request_id = get_request_id()
    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id, "path": request.url.path},
    )

    return _build_error_response(
        500,
        "INTERNAL_ERROR",
        "An unexpected error occurred",
    )


# =============================================================================
# Middleware Configuration
# =============================================================================

# Configure CORS middleware
if RAG_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=RAG_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

# Add middleware (note: middleware runs in reverse order of registration)
# So we register logging first, then request ID, so request ID runs first
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)


# =============================================================================
# Route Registration
# =============================================================================

# Register routers
app.include_router(health_router)
app.include_router(query_router)
app.include_router(sources_router)
app.include_router(slack_router)
