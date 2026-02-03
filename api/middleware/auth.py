# api/middleware/auth.py
"""Authentication middleware for the License Intelligence API.

Provides two authentication methods:
1. API Key Authentication: Bearer token for /query and /sources endpoints
2. Slack Signature Verification: HMAC-SHA256 for /slack/command endpoint
"""

import hashlib
import hmac
import time

from fastapi import Header
from fastapi import Request

from api.config import RAG_API_KEY
from api.config import SLACK_SIGNING_SECRET
from api.exceptions import UnauthorizedError


def get_api_key(authorization: str | None = Header(None)) -> str:
    """Verify API key from Authorization header.

    Extracts and validates Bearer token from Authorization header.
    Used for /query and /sources endpoints.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>").

    Returns:
        Validated API key.

    Raises:
        UnauthorizedError: If authorization is missing, malformed, or invalid.
    """
    if not authorization:
        raise UnauthorizedError(
            message="Missing Authorization header",
            details={"expected_format": "Bearer <api_key>"},
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(
            message="Invalid Authorization header format",
            details={"expected_format": "Bearer <api_key>"},
        )

    provided_key = parts[1]

    # Validate against configured API key
    if not RAG_API_KEY:
        raise UnauthorizedError(
            message="API authentication not configured",
            details={"reason": "RAG_API_KEY environment variable not set"},
        )

    if not hmac.compare_digest(provided_key, RAG_API_KEY):
        raise UnauthorizedError(
            message="Invalid API key",
            details={"reason": "Provided key does not match configured RAG_API_KEY"},
        )

    return provided_key


async def verify_slack_signature_async(
    request: Request,
    x_slack_signature: str | None = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(
        None, alias="X-Slack-Request-Timestamp"
    ),
) -> None:
    """Async version of verify_slack_signature that can access request body.

    Validates that request came from Slack by verifying HMAC-SHA256 signature.
    Implements replay attack protection by checking timestamp is within 5 minutes.

    Args:
        request: FastAPI request object (for accessing body).
        x_slack_signature: Slack signature from X-Slack-Signature header.
        x_slack_request_timestamp: Request timestamp from X-Slack-Request-Timestamp header.

    Raises:
        UnauthorizedError: If signature is missing, invalid, or timestamp is expired.

    References:
        https://api.slack.com/authentication/verifying-requests-from-slack
    """
    # Check headers are present
    if not x_slack_signature:
        raise UnauthorizedError(
            message="Missing Slack signature",
            details={"required_header": "X-Slack-Signature"},
        )

    if not x_slack_request_timestamp:
        raise UnauthorizedError(
            message="Missing Slack request timestamp",
            details={"required_header": "X-Slack-Request-Timestamp"},
        )

    # Check signing secret is configured
    if not SLACK_SIGNING_SECRET:
        raise UnauthorizedError(
            message="Slack authentication not configured",
            details={"reason": "SLACK_SIGNING_SECRET environment variable not set"},
        )

    # Validate timestamp is within 5 minutes (replay attack protection)
    try:
        request_timestamp = int(x_slack_request_timestamp)
    except ValueError:
        raise UnauthorizedError(
            message="Invalid Slack request timestamp",
            details={"reason": "Timestamp must be a Unix timestamp integer"},
        )

    current_timestamp = int(time.time())
    if abs(current_timestamp - request_timestamp) > 60 * 5:  # 5 minutes
        raise UnauthorizedError(
            message="Slack request timestamp expired",
            details={
                "reason": "Request timestamp is more than 5 minutes old (replay attack protection)",
                "max_age_seconds": 300,
            },
        )

    # Read request body
    body = await request.body()

    # Compute expected signature
    # Format: v0=<hash> where hash is HMAC-SHA256 of "v0:{timestamp}:{body}"
    sig_basestring = f"v0:{x_slack_request_timestamp}:{body.decode('utf-8')}"
    expected_signature = (
        "v0="
        + hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    # Compare signatures using constant-time comparison
    if not hmac.compare_digest(expected_signature, x_slack_signature):
        raise UnauthorizedError(
            message="Invalid Slack signature",
            details={"reason": "Signature verification failed"},
        )
