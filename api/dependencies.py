# api/dependencies.py
"""FastAPI dependencies for the License Intelligence API.

Provides reusable dependencies for authentication, rate limiting, and other
cross-cutting concerns.
"""

from fastapi import Depends
from fastapi import Header
from fastapi import Request

from api.middleware.auth import get_api_key
from api.middleware.auth import verify_slack_signature_async


async def authenticate(
    request: Request,
    authorization: str | None = Header(None),
    x_slack_signature: str | None = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(
        None, alias="X-Slack-Request-Timestamp"
    ),
) -> dict[str, str]:
    """Authenticate request with API key (Bearer token).

    Validates Bearer token from Authorization header against RAG_API_KEY.
    Use this dependency on endpoints that require API key authentication.

    SECURITY WARNING: Test mode (RAG_TEST_MODE=true) bypasses authentication.
    Never enable test mode in production!

    Args:
        request: FastAPI request object.
        authorization: Authorization header (for API key auth).
        x_slack_signature: Slack signature header (unused, kept for compatibility).
        x_slack_request_timestamp: Slack timestamp header (unused, kept for compatibility).

    Returns:
        Authentication context dict with:
        - type: "api_key" | "none"
        - (for api_key) key: The validated API key

    Raises:
        UnauthorizedError: If authentication fails.
    """
    from api.config import RAG_TEST_MODE

    # SECURITY: Only skip auth if RAG_TEST_MODE is explicitly enabled
    # This prevents accidental auth bypass from missing RAG_API_KEY in production
    if RAG_TEST_MODE:
        request.state.auth_type = "none"
        request.state.auth_context = {"type": "none"}
        return {"type": "none"}

    api_key = get_api_key(authorization)
    auth_context = {"type": "api_key", "key": api_key}
    request.state.auth_type = "api_key"
    request.state.auth_context = auth_context
    return auth_context


async def authenticate_slack(
    request: Request,
    x_slack_signature: str | None = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(
        None, alias="X-Slack-Request-Timestamp"
    ),
) -> dict[str, str]:
    """Authenticate Slack request with signature verification.

    Validates HMAC-SHA256 signature from Slack headers.
    Use this dependency on /slack/* endpoints.

    Args:
        request: FastAPI request object.
        x_slack_signature: Slack signature from X-Slack-Signature header.
        x_slack_request_timestamp: Request timestamp from X-Slack-Request-Timestamp header.

    Returns:
        Authentication context dict with type="slack".

    Raises:
        UnauthorizedError: If signature verification fails.
    """
    await verify_slack_signature_async(
        request, x_slack_signature, x_slack_request_timestamp
    )
    auth_context = {"type": "slack"}
    request.state.auth_type = "slack"
    request.state.auth_context = auth_context
    return auth_context


# Convenience dependency for endpoints that require API key only
RequireAPIKey = Depends(lambda authorization: get_api_key(authorization=authorization))
