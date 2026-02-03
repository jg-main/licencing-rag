# api/middleware/rate_limit.py
"""Rate limiting middleware for the License Intelligence API.

Implements in-memory token bucket rate limiting per API key or IP address.
For production multi-instance deployments, consider using Redis-backed storage.
"""

import time
from typing import Any

from fastapi import Request

from api.config import RAG_RATE_LIMIT
from api.config import TRUST_PROXY_HEADERS
from api.exceptions import RateLimitError
from app.logging import get_logger

log = get_logger(__name__)


class TokenBucket:
    """Token bucket algorithm for rate limiting.

    Allows bursts while maintaining average rate limit.
    """

    def __init__(self, capacity: int, refill_rate: float) -> None:
        """Initialize token bucket.

        Args:
            capacity: Maximum tokens (burst limit).
            refill_rate: Tokens added per second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens: float = float(capacity)
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens were consumed, False if insufficient tokens.
        """
        now = time.time()

        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def remaining(self) -> int:
        """Get remaining tokens.

        Returns:
            Number of tokens currently available.
        """
        return int(self.tokens)

    def reset_time(self) -> int:
        """Get time until bucket is full.

        Returns:
            Seconds until bucket reaches capacity (Unix timestamp).
        """
        now = time.time()

        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        current_tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if current_tokens >= self.capacity:
            return int(now)

        tokens_needed = self.capacity - current_tokens
        seconds_to_full = tokens_needed / self.refill_rate
        return int(now + seconds_to_full)


class RateLimiter:
    """In-memory rate limiter using token bucket algorithm.

    Implements simple LRU eviction to prevent unbounded memory growth.
    For production: Consider using Redis for distributed rate limiting
    across multiple instances/workers.
    """

    # Maximum number of buckets to keep in memory
    MAX_BUCKETS = 10000

    def __init__(self, rate_limit: int = RAG_RATE_LIMIT) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Requests per minute per key.
        """
        self.rate_limit = rate_limit
        # Convert to requests per second for token bucket
        self.refill_rate = rate_limit / 60.0
        # Allow small bursts (10 requests)
        self.burst_capacity = min(10, rate_limit)
        self.buckets: dict[str, TokenBucket] = {}
        # Track access order for LRU eviction
        self.access_order: list[str] = []

    def _evict_oldest(self) -> None:
        """Remove least recently used bucket when max capacity reached."""
        if len(self.buckets) >= self.MAX_BUCKETS and self.access_order:
            oldest_key = self.access_order.pop(0)
            self.buckets.pop(oldest_key, None)
            log.debug(
                "rate_limiter_evicted_bucket",
                evicted_key=oldest_key,
                buckets_count=len(self.buckets),
            )

    def _touch(self, key: str) -> None:
        """Mark bucket as recently used (LRU tracking).

        Args:
            key: Rate limit key being accessed.
        """
        # Remove from current position if exists
        if key in self.access_order:
            self.access_order.remove(key)
        # Add to end (most recently used)
        self.access_order.append(key)

    def check_limit(self, key: str) -> tuple[bool, dict[str, Any]]:
        """Check if request should be allowed.

        Args:
            key: Rate limit key (API key or IP address).

        Returns:
            Tuple of (allowed, headers_dict) where headers_dict contains
            rate limit headers to add to response.
        """
        # Evict oldest bucket if at capacity
        if key not in self.buckets:
            self._evict_oldest()
            self.buckets[key] = TokenBucket(self.burst_capacity, self.refill_rate)

        # Mark as recently used (LRU)
        self._touch(key)

        bucket = self.buckets[key]

        # Try to consume a token
        allowed = bucket.consume(1)

        # Get reset timestamp
        reset_timestamp = bucket.reset_time()

        # Prepare rate limit headers
        headers = {
            "X-RateLimit-Limit": str(self.rate_limit),
            "X-RateLimit-Remaining": str(max(0, bucket.remaining())),
            "X-RateLimit-Reset": str(reset_timestamp),
        }

        if not allowed:
            # Retry-After is seconds from now, not a timestamp
            retry_after_seconds = max(0, reset_timestamp - int(time.time()))
            headers["Retry-After"] = str(retry_after_seconds)

        return allowed, headers


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limit_key(request: Request) -> str:
    """Extract rate limit key from request.

    Uses X-Forwarded-For only when TRUST_PROXY_HEADERS is enabled to prevent
    IP spoofing when not behind a trusted proxy.

    Args:
        request: FastAPI request object.

    Returns:
        Rate limit key string.
    """
    # Try to get API key from request state (set by auth dependency)
    auth_context = getattr(request.state, "auth_context", None)
    if auth_context and auth_context.get("type") == "api_key":
        api_key = auth_context.get("key", "")
        if api_key:
            return f"api_key:{api_key}"

    # Fall back to client IP
    # Only trust X-Forwarded-For when behind a trusted proxy (ALB, nginx, etc.)
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For format: "client, proxy1, proxy2"
            # First IP is the original client
            client_ip = forwarded.split(",")[0].strip()
            return f"ip:{client_ip}"

    # Direct connection IP (no proxy)
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


async def check_rate_limit(request: Request) -> dict[str, Any]:
    """Rate limiting dependency.

    Checks if request is within rate limit and adds headers to response.
    Always sets rate_limit_headers in request.state before raising to ensure
    429 responses include required headers.

    Args:
        request: FastAPI request object.

    Returns:
        Dict with rate limit headers to add to response.

    Raises:
        RateLimitError: If rate limit exceeded.
    """
    try:
        key = get_rate_limit_key(request)
        allowed, headers = _rate_limiter.check_limit(key)

        # ALWAYS store headers in request state before any potential raise
        # This ensures 429 responses include X-RateLimit-* headers
        request.state.rate_limit_headers = headers

        if not allowed:
            reset_time = int(headers["Retry-After"])
            raise RateLimitError(
                message=f"Rate limit exceeded. Try again in {reset_time} seconds.",
                retry_after=reset_time,
            )

        return headers
    except RateLimitError:
        # Re-raise RateLimitError as-is (headers already set)
        raise
    except Exception as e:
        # On unexpected error, set default headers so response isn't broken
        # Log the error to surface rate limiter internal failures
        log.error(
            "rate_limiter_unexpected_error",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(_rate_limiter.rate_limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time() + 60)),
            "Retry-After": "60",  # Default retry window
        }
        raise
