# api/exceptions.py
"""Custom exception classes for the License Intelligence API.

All custom exceptions inherit from APIError and include:
- HTTP status code
- Error code (for client identification)
- Human-readable message
- Optional details dictionary for additional context
"""

from typing import Any


class APIError(Exception):
    """Base exception for all API errors.

    Attributes:
        status_code: HTTP status code to return.
        code: Machine-readable error code (e.g., 'VALIDATION_ERROR').
        message: Human-readable error message.
        details: Optional dictionary with additional error context.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code (default: 500).
            code: Error code for client identification.
            details: Optional additional error context.
        """
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class ValidationError(APIError):
    """Raised when request validation fails (400 Bad Request).

    Use for invalid request parameters, malformed input, or constraint violations.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Description of validation failure.
            details: Optional validation error details.
        """
        super().__init__(
            message=message,
            status_code=400,
            code="VALIDATION_ERROR",
            details=details,
        )


class EmptyQuestionError(APIError):
    """Raised when question is empty or whitespace-only (400 Bad Request).

    Special case of validation error for empty questions.
    """

    def __init__(self, details: dict[str, Any] | None = None) -> None:
        """Initialize empty question error.

        Args:
            details: Optional additional context.
        """
        super().__init__(
            message="Question cannot be empty or whitespace-only",
            status_code=400,
            code="EMPTY_QUESTION",
            details=details,
        )


class UnauthorizedError(APIError):
    """Raised when authentication is missing or invalid (401 Unauthorized).

    Use for missing API keys, invalid tokens, or failed Slack signature verification.
    """

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize unauthorized error.

        Args:
            message: Description of authentication failure.
            details: Optional additional context.
        """
        super().__init__(
            message=message,
            status_code=401,
            code="UNAUTHORIZED",
            details=details,
        )


class ForbiddenError(APIError):
    """Raised when authenticated user lacks permission (403 Forbidden).

    Use for valid authentication but insufficient permissions.
    """

    def __init__(
        self, message: str = "Access forbidden", details: dict[str, Any] | None = None
    ) -> None:
        """Initialize forbidden error.

        Args:
            message: Description of permission failure.
            details: Optional additional context.
        """
        super().__init__(
            message=message,
            status_code=403,
            code="FORBIDDEN",
            details=details,
        )


class SourceNotFoundError(APIError):
    """Raised when specified source does not exist (404 Not Found).

    Use when client requests unknown data sources.
    """

    def __init__(self, source: str | list[str], available_sources: list[str]) -> None:
        """Initialize source not found error.

        Args:
            source: Unknown source name(s).
            available_sources: List of valid source names.
        """
        if isinstance(source, list):
            source_str = ", ".join(source)
            message = f"Unknown sources: {source_str}"
        else:
            message = f"Unknown source: {source}"

        super().__init__(
            message=message,
            status_code=404,
            code="SOURCE_NOT_FOUND",
            details={"available_sources": available_sources},
        )


class RateLimitError(APIError):
    """Raised when rate limit is exceeded (429 Too Many Requests).

    Use when client exceeds request quota.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        """Initialize rate limit error.

        Args:
            message: Description of rate limit violation.
            retry_after: Seconds until rate limit resets.
        """
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            message=message,
            status_code=429,
            code="RATE_LIMITED",
            details=details,
        )


class OpenAIError(APIError):
    """Raised when OpenAI API call fails (502 Bad Gateway).

    Use for upstream OpenAI errors, timeouts, or service unavailability.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize OpenAI error.

        Args:
            message: Description of OpenAI failure.
            details: Optional error details from OpenAI.
        """
        super().__init__(
            message=f"OpenAI API error: {message}",
            status_code=502,
            code="OPENAI_ERROR",
            details=details,
        )


class ServiceUnavailableError(APIError):
    """Raised when service dependencies are unavailable (503 Service Unavailable).

    Use for missing indexes, database connection failures, or configuration errors.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize service unavailable error.

        Args:
            message: Description of service failure.
            details: Optional additional context.
        """
        super().__init__(
            message=message,
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            details=details,
        )
