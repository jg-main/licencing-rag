# tests/test_api_auth.py
"""Tests for API authentication."""

import hashlib
import hmac
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
        # Also patch in middleware module since it imports at module level
        with patch("api.middleware.auth.RAG_API_KEY", TEST_API_KEY):
            yield


class TestHealthEndpointsNoAuth:
    """Test that health endpoints don't require authentication."""

    def test_health_no_auth_required(self, client: TestClient) -> None:
        """Test /health works without authentication."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ready_no_auth_required(self, client: TestClient) -> None:
        """Test /ready works without authentication."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert "status" in response.json()

    def test_version_no_auth_required(self, client: TestClient) -> None:
        """Test /version works without authentication."""
        response = client.get("/version")
        assert response.status_code == 200
        assert "api_version" in response.json()


@pytest.mark.requires_auth
class TestAPIKeyAuthentication:
    """Test API key authentication for /query and /sources endpoints."""

    def test_query_requires_auth(self, client: TestClient) -> None:
        """Test /query returns 401 without authentication."""
        response = client.post("/query", json={"question": "test query"})
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "authorization" in data["error"]["message"].lower()

    def test_query_with_valid_api_key(self, client: TestClient) -> None:
        """Test /query succeeds with valid API key."""
        # Note: This will fail with index errors, but should pass auth (401 → 503)
        response = client.post(
            "/query",
            json={"question": "test query"},
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        # Should get past auth (not 401), but fail on missing index (503)
        assert response.status_code != 401

    def test_query_with_invalid_api_key(self, client: TestClient) -> None:
        """Test /query returns 401 with invalid API key."""
        response = client.post(
            "/query",
            json={"question": "test query"},
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "invalid" in data["error"]["message"].lower()

    def test_query_with_malformed_header(self, client: TestClient) -> None:
        """Test /query returns 401 with malformed Authorization header."""
        response = client.post(
            "/query",
            json={"question": "test query"},
            headers={"Authorization": "NotBearer token"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "format" in data["error"]["message"].lower()

    def test_query_with_missing_bearer_prefix(self, client: TestClient) -> None:
        """Test /query returns 401 when Bearer prefix is missing."""
        response = client.post(
            "/query",
            json={"question": "test query"},
            headers={"Authorization": TEST_API_KEY},  # Missing "Bearer "
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_sources_requires_auth(self, client: TestClient) -> None:
        """Test /sources returns 401 without authentication."""
        response = client.get("/sources")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_sources_with_valid_api_key(self, client: TestClient) -> None:
        """Test /sources succeeds with valid API key."""
        response = client.get(
            "/sources",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert response.status_code == 200
        assert "sources" in response.json()

    def test_source_documents_requires_auth(self, client: TestClient) -> None:
        """Test /sources/{name} returns 401 without authentication."""
        response = client.get("/sources/cme")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_source_documents_with_valid_api_key(self, client: TestClient) -> None:
        """Test /sources/{name} succeeds with valid API key."""
        response = client.get(
            "/sources/cme",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        # Should get past auth (not 401)
        assert response.status_code != 401


@pytest.mark.requires_auth
class TestAPIKeyNotConfigured:
    """Test behavior when RAG_API_KEY is not configured."""

    def test_query_fails_when_api_key_not_set(self, client: TestClient) -> None:
        """Test /query returns 401 when RAG_API_KEY is not configured."""
        with patch("api.middleware.auth.RAG_API_KEY", None):
            response = client.post(
                "/query",
                json={"question": "test query"},
                headers={"Authorization": "Bearer some-key"},
            )
            assert response.status_code == 401
            data = response.json()
            assert data["error"]["code"] == "UNAUTHORIZED"
            assert "not configured" in data["error"]["message"].lower()


class TestSlackSignatureVerification:
    """Test Slack signature verification for /slack/command endpoint."""

    def _generate_slack_signature(self, timestamp: str, body: str, secret: str) -> str:
        """Generate valid Slack signature for testing.

        Args:
            timestamp: Unix timestamp as string.
            body: Request body.
            secret: Slack signing secret.

        Returns:
            Slack signature in format "v0=<hex_digest>".
        """
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = hmac.new(
            secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"v0={signature}"

    def test_slack_endpoint_requires_signature(self, client: TestClient) -> None:
        """Test /slack/command returns 401 without Slack signature."""
        # Note: This endpoint doesn't exist yet (Phase 6), so we'll get 404
        # But we can still test the auth dependency logic
        response = client.post("/slack/command", data={"text": "test"})
        # Will be 404 (not found) since endpoint doesn't exist yet
        # But if auth was checked first, it would be 401
        # For now, just verify we don't get a 200
        assert response.status_code != 200

    def test_slack_signature_missing_headers(self, client: TestClient) -> None:
        """Test Slack auth fails when headers are missing."""
        # This will be tested once /slack/command endpoint is implemented in Phase 6
        pass

    def test_slack_signature_expired_timestamp(self, client: TestClient) -> None:
        """Test Slack auth fails when timestamp is too old."""
        # This will be tested once /slack/command endpoint is implemented in Phase 6
        pass

    def test_slack_signature_invalid(self, client: TestClient) -> None:
        """Test Slack auth fails with invalid signature."""
        # This will be tested once /slack/command endpoint is implemented in Phase 6
        pass

    def test_slack_signature_valid(self, client: TestClient) -> None:
        """Test Slack auth succeeds with valid signature."""
        # This will be tested once /slack/command endpoint is implemented in Phase 6
        pass


class TestAuthenticationContext:
    """Test authentication context returned by authenticate dependency."""

    def test_api_key_auth_returns_context(self, client: TestClient) -> None:
        """Test that API key auth includes auth context."""
        # The auth context is internal to the endpoint
        # We can verify it works by checking the endpoint succeeds
        response = client.get(
            "/sources",
            headers={"Authorization": f"Bearer {TEST_API_KEY}"},
        )
        assert response.status_code == 200

    def test_health_endpoints_return_none_auth_type(self, client: TestClient) -> None:
        """Test that health endpoints don't require auth context."""
        response = client.get("/health")
        assert response.status_code == 200


@pytest.mark.requires_auth
class TestErrorResponseFormat:
    """Test authentication error responses follow consistent format."""

    def test_auth_error_has_request_id(self, client: TestClient) -> None:
        """Test authentication errors include request ID."""
        response = client.post("/query", json={"question": "test"})
        assert response.status_code == 401
        data = response.json()

        # Request ID should be in body and header
        assert "request_id" in data
        assert "X-Request-ID" in response.headers

    def test_auth_error_has_consistent_structure(self, client: TestClient) -> None:
        """Test authentication errors follow ErrorResponse schema."""
        response = client.post("/query", json={"question": "test"})
        assert response.status_code == 401
        data = response.json()

        # Required fields
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "message" in data["error"]

    def test_auth_error_includes_details(self, client: TestClient) -> None:
        """Test authentication errors include helpful details."""
        response = client.post("/query", json={"question": "test"})
        assert response.status_code == 401
        data = response.json()

        # Should include details about expected format
        assert "details" in data["error"]
        assert "expected_format" in data["error"]["details"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
