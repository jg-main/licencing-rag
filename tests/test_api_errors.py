# tests/test_api_errors.py
"""Tests for API error handling and validation."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestValidationErrors:
    """Test validation error handling."""

    def test_empty_request_body(self) -> None:
        """Test that empty request body returns 400 validation error."""
        response = client.post("/query", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "question" in data["error"]["message"].lower()

    def test_empty_question(self) -> None:
        """Test that empty question returns 400 validation error."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "empty" in data["error"]["message"].lower()

    def test_whitespace_only_question(self) -> None:
        """Test that whitespace-only question returns 400 validation error."""
        response = client.post("/query", json={"question": "   \n\t  "})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_source(self) -> None:
        """Test that invalid source returns 404 SOURCE_NOT_FOUND error."""
        response = client.post(
            "/query", json={"question": "test query", "sources": ["invalid_source"]}
        )
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"
        assert "invalid_source" in data["error"]["message"]
        assert "available_sources" in data["error"]["details"]

    def test_multiple_invalid_sources(self) -> None:
        """Test that multiple invalid sources are reported."""
        response = client.post(
            "/query",
            json={"question": "test query", "sources": ["invalid1", "invalid2"]},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"
        # Both invalid sources should be mentioned
        assert (
            "invalid1" in data["error"]["message"]
            or "invalid2" in data["error"]["message"]
        )

    def test_invalid_search_mode(self) -> None:
        """Test that invalid search_mode returns 400 validation error."""
        response = client.post(
            "/query",
            json={
                "question": "test query",
                "options": {"search_mode": "invalid_mode"},
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_top_k_too_low(self) -> None:
        """Test that top_k < 1 returns validation error."""
        response = client.post(
            "/query",
            json={"question": "test query", "options": {"top_k": 0}},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_top_k_too_high(self) -> None:
        """Test that top_k > 50 returns validation error."""
        response = client.post(
            "/query",
            json={"question": "test query", "options": {"top_k": 100}},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_json(self) -> None:
        """Test that malformed JSON returns 400 validation error."""
        response = client.post(
            "/query",
            content=b"{ invalid json }",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_question_too_long(self) -> None:
        """Test that question exceeding max_length returns validation error."""
        long_question = "a" * 2001  # max_length is 2000
        response = client.post("/query", json={"question": long_question})
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == "VALIDATION_ERROR"


class TestSourcesEndpointErrors:
    """Test error handling for sources endpoints."""

    def test_get_nonexistent_source(self) -> None:
        """Test that requesting nonexistent source returns 404."""
        response = client.get("/sources/nonexistent_source")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"
        assert "nonexistent_source" in data["error"]["message"]
        assert "available_sources" in data["error"]["details"]


class TestErrorResponseFormat:
    """Test error response format consistency."""

    def test_error_has_request_id(self) -> None:
        """Test that error responses include request ID."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 400
        data = response.json()

        # Request ID should be in body and header
        assert "request_id" in data
        assert "X-Request-ID" in response.headers
        assert data["request_id"] == response.headers["X-Request-ID"]

    def test_error_format_structure(self) -> None:
        """Test that error responses have consistent structure."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 400
        data = response.json()

        # Required fields
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

        # Optional details field
        if "details" in data["error"]:
            assert isinstance(data["error"]["details"], dict)

    def test_validation_error_includes_field_info(self) -> None:
        """Test that Pydantic validation errors include field details."""
        response = client.post(
            "/query", json={"question": "test", "options": {"top_k": 0}}
        )
        assert response.status_code == 400
        data = response.json()

        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in data["error"]
        assert "errors" in data["error"]["details"]

        # Should have error info
        errors = data["error"]["details"]["errors"]
        assert len(errors) > 0
        assert "field" in errors[0]
        assert "reason" in errors[0]


class TestHTTPExceptionHandling:
    """Test handling of standard HTTP exceptions."""

    def test_404_endpoint(self) -> None:
        """Test that 404 on unknown endpoint returns consistent format."""
        response = client.get("/nonexistent_endpoint")
        assert response.status_code == 404
        data = response.json()

        # Should still follow error format
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "HTTP_404"


class TestExceptionClasses:
    """Test custom exception classes directly."""

    def test_api_error_attributes(self) -> None:
        """Test APIError has correct attributes."""
        from api.exceptions import APIError

        exc = APIError(
            message="Test error",
            status_code=500,
            code="TEST_ERROR",
            details={"key": "value"},
        )

        assert exc.status_code == 500
        assert exc.code == "TEST_ERROR"
        assert exc.message == "Test error"
        assert exc.details == {"key": "value"}

    def test_empty_question_error(self) -> None:
        """Test EmptyQuestionError has correct defaults."""
        from api.exceptions import EmptyQuestionError

        exc = EmptyQuestionError()

        assert exc.status_code == 400
        assert exc.code == "EMPTY_QUESTION"
        assert "empty" in exc.message.lower()

    def test_source_not_found_error_single_source(self) -> None:
        """Test SourceNotFoundError with single source."""
        from api.exceptions import SourceNotFoundError

        exc = SourceNotFoundError(source="test", available_sources=["cme", "opra"])

        assert exc.status_code == 404
        assert exc.code == "SOURCE_NOT_FOUND"
        assert "test" in exc.message
        assert exc.details == {"available_sources": ["cme", "opra"]}

    def test_source_not_found_error_multiple_sources(self) -> None:
        """Test SourceNotFoundError with multiple sources."""
        from api.exceptions import SourceNotFoundError

        exc = SourceNotFoundError(
            source=["test1", "test2"], available_sources=["cme", "opra"]
        )

        assert exc.status_code == 404
        assert exc.code == "SOURCE_NOT_FOUND"
        assert "test1" in exc.message
        assert "test2" in exc.message

    def test_rate_limit_error(self) -> None:
        """Test RateLimitError includes retry_after."""
        from api.exceptions import RateLimitError

        exc = RateLimitError(retry_after=60)

        assert exc.status_code == 429
        assert exc.code == "RATE_LIMITED"
        assert exc.details == {"retry_after": 60}

    def test_openai_error(self) -> None:
        """Test OpenAIError formats message correctly."""
        from api.exceptions import OpenAIError

        exc = OpenAIError(message="Connection timeout")

        assert exc.status_code == 502
        assert exc.code == "OPENAI_ERROR"
        assert "OpenAI API error" in exc.message
        assert "Connection timeout" in exc.message

    def test_service_unavailable_error(self) -> None:
        """Test ServiceUnavailableError."""
        from api.exceptions import ServiceUnavailableError

        exc = ServiceUnavailableError(
            message="Index not found", details={"index_path": "/path/to/index"}
        )

        assert exc.status_code == 503
        assert exc.code == "SERVICE_UNAVAILABLE"
        assert "Index not found" in exc.message
        assert exc.details == {"index_path": "/path/to/index"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
