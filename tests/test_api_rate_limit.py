# tests/test_api_rate_limit.py
"""Tests for API rate limiting."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

# Test API key
TEST_API_KEY = "test-api-key-12345"


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_api_key():
    """Mock RAG_API_KEY environment variable for all tests."""
    with patch("api.config.RAG_API_KEY", TEST_API_KEY):
        with patch("api.middleware.auth.RAG_API_KEY", TEST_API_KEY):
            yield


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create authentication headers for API requests."""
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.mark.requires_auth
class TestRateLimitHeaders:
    """Test that rate limit headers are included in responses."""

    def test_query_includes_rate_limit_headers(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that rate-limited endpoints include rate limit headers."""
        response = client.get("/sources", headers=auth_headers)

        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

        # Validate header values
        assert int(response.headers["X-RateLimit-Limit"]) > 0
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0
        # Reset time should be close to now (within 10 seconds tolerance for slow tests)
        reset_time = int(response.headers["X-RateLimit-Reset"])
        now = int(time.time())
        assert reset_time >= now - 10, (
            f"Reset time {reset_time} is too far in past (now={now})"
        )

    def test_sources_includes_rate_limit_headers(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that /sources responses include rate limit headers."""
        response = client.get("/sources", headers=auth_headers)

        # Should have rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_health_does_not_include_rate_limit_headers(
        self, client: TestClient
    ) -> None:
        """Test that health endpoints don't include rate limit headers."""
        response = client.get("/health")

        # Health endpoint should NOT have rate limit headers (no rate limiting)
        assert "X-RateLimit-Limit" not in response.headers
        assert "X-RateLimit-Remaining" not in response.headers


@pytest.mark.requires_auth
class TestRateLimitBehavior:
    """Test rate limiting behavior."""

    def test_rate_limit_decrements(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that remaining count decrements with each request."""
        # Make first request
        response1 = client.get("/sources", headers=auth_headers)
        remaining1 = int(response1.headers["X-RateLimit-Remaining"])

        # Make second request
        response2 = client.get("/sources", headers=auth_headers)
        remaining2 = int(response2.headers["X-RateLimit-Remaining"])

        # Remaining should decrease
        assert remaining2 < remaining1

    def test_exceeding_rate_limit_returns_429(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that exceeding rate limit returns 429."""
        # Configure very low rate limit for testing
        with patch("api.middleware.rate_limit.RAG_RATE_LIMIT", 2):
            # Reset rate limiter with new limit
            from api.middleware.rate_limit import RateLimiter

            rate_limiter = RateLimiter(rate_limit=2)

            with patch("api.middleware.rate_limit._rate_limiter", rate_limiter):
                # Make requests until we hit the limit
                # Burst capacity is min(10, rate_limit) = 2
                # So we can make 2 requests, 3rd should fail
                response1 = client.get("/sources", headers=auth_headers)
                assert response1.status_code == 200

                response2 = client.get("/sources", headers=auth_headers)
                assert response2.status_code == 200

                # Third request should be rate limited
                response3 = client.get("/sources", headers=auth_headers)
                assert response3.status_code == 429

    def test_rate_limit_error_includes_retry_after(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that 429 response includes Retry-After header."""
        with patch("api.middleware.rate_limit.RAG_RATE_LIMIT", 2):
            from api.middleware.rate_limit import RateLimiter

            rate_limiter = RateLimiter(rate_limit=2)

            with patch("api.middleware.rate_limit._rate_limiter", rate_limiter):
                # Exhaust rate limit
                client.get("/sources", headers=auth_headers)
                client.get("/sources", headers=auth_headers)

                # Get rate limited
                response = client.get("/sources", headers=auth_headers)
                assert response.status_code == 429

                # Should have Retry-After header
                assert "Retry-After" in response.headers
                retry_after = int(response.headers["Retry-After"])
                assert retry_after > 0

    def test_rate_limit_error_response_format(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that rate limit error follows standard error format."""
        with patch("api.middleware.rate_limit.RAG_RATE_LIMIT", 2):
            from api.middleware.rate_limit import RateLimiter

            rate_limiter = RateLimiter(rate_limit=2)

            with patch("api.middleware.rate_limit._rate_limiter", rate_limiter):
                # Exhaust rate limit
                client.get("/sources", headers=auth_headers)
                client.get("/sources", headers=auth_headers)

                # Get rate limited
                response = client.get("/sources", headers=auth_headers)
                assert response.status_code == 429

                data = response.json()
                assert data["success"] is False
                assert data["error"]["code"] == "RATE_LIMITED"
                assert "rate limit" in data["error"]["message"].lower()
                assert "details" in data["error"]
                assert "retry_after" in data["error"]["details"]
                assert "retry_after" in data["error"]["details"]


@pytest.mark.requires_auth
class TestRateLimitByKey:
    """Test that rate limits are per API key."""

    def test_different_api_keys_have_separate_limits(self, client: TestClient) -> None:
        """Test that different API keys have independent rate limits."""
        with patch("api.middleware.rate_limit.RAG_RATE_LIMIT", 2):
            from api.middleware.rate_limit import RateLimiter

            rate_limiter = RateLimiter(rate_limit=2)

            with patch("api.middleware.rate_limit._rate_limiter", rate_limiter):
                # Exhaust limit for first key
                headers1 = {"Authorization": f"Bearer {TEST_API_KEY}"}
                client.get("/sources", headers=headers1)
                client.get("/sources", headers=headers1)
                response1 = client.get("/sources", headers=headers1)
                assert response1.status_code == 429

                # Second key should still work
                with patch("api.config.RAG_API_KEY", "different-key"):
                    with patch("api.middleware.auth.RAG_API_KEY", "different-key"):
                        headers2 = {"Authorization": "Bearer different-key"}
                        response2 = client.get("/sources", headers=headers2)
                        assert response2.status_code == 200


class TestRateLimitResetBehavior:
    """Test rate limit reset and refill behavior."""

    def test_rate_limit_refills_over_time(self) -> None:
        """Test that token bucket refills over time."""
        from api.middleware.rate_limit import TokenBucket

        # Create bucket with 2 capacity, 1 token/second refill
        bucket = TokenBucket(capacity=2, refill_rate=1.0)

        # Consume all tokens
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False  # No more tokens

        # Wait for refill (1+ second should add 1+ token)
        time.sleep(1.1)

        # Should be able to consume again
        assert bucket.consume(1) is True

    def test_rate_limit_reset_header_accurate(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that X-RateLimit-Reset header is accurate."""
        response = client.get("/sources", headers=auth_headers)

        reset_time = int(response.headers["X-RateLimit-Reset"])
        current_time = int(time.time())

        # Reset time should be in the future (within reasonable bounds)
        assert reset_time >= current_time
        assert reset_time <= current_time + 3600  # Within 1 hour


class TestRateLimitEviction:
    """Test LRU eviction to prevent unbounded memory growth."""

    def test_buckets_evicted_when_max_reached(self) -> None:
        """Test that oldest buckets are evicted when MAX_BUCKETS is reached."""
        from api.middleware.rate_limit import RateLimiter

        # Create rate limiter with very low max buckets for testing
        with patch.object(RateLimiter, "MAX_BUCKETS", 3):
            rate_limiter = RateLimiter(rate_limit=100)

            # Add 3 buckets
            rate_limiter.check_limit("key1")
            rate_limiter.check_limit("key2")
            rate_limiter.check_limit("key3")
            assert len(rate_limiter.buckets) == 3

            # Adding 4th should evict oldest (key1)
            rate_limiter.check_limit("key4")
            assert len(rate_limiter.buckets) == 3
            assert "key1" not in rate_limiter.buckets
            assert "key2" in rate_limiter.buckets
            assert "key3" in rate_limiter.buckets
            assert "key4" in rate_limiter.buckets

            # Access key2 to make it most recent
            rate_limiter.check_limit("key2")

            # Adding 5th should evict key3 (now oldest)
            rate_limiter.check_limit("key5")
            assert len(rate_limiter.buckets) == 3
            assert "key3" not in rate_limiter.buckets
            assert "key2" in rate_limiter.buckets
            assert "key4" in rate_limiter.buckets
            assert "key5" in rate_limiter.buckets

    def test_buckets_below_max_not_evicted(self) -> None:
        """Test that buckets are not evicted when below MAX_BUCKETS."""
        from api.middleware.rate_limit import RateLimiter

        with patch.object(RateLimiter, "MAX_BUCKETS", 10):
            rate_limiter = RateLimiter(rate_limit=100)

            # Add 5 buckets (below max)
            for i in range(5):
                rate_limiter.check_limit(f"key{i}")

            # All should still exist
            assert len(rate_limiter.buckets) == 5
            for i in range(5):
                assert f"key{i}" in rate_limiter.buckets
