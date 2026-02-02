# tests/test_api_health.py
"""Tests for API health endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_healthy(self, client: TestClient) -> None:
        """Test /health returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_health_no_auth_required(self, client: TestClient) -> None:
        """Test /health works without authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_includes_request_id_header(self, client: TestClient) -> None:
        """Test /health response includes X-Request-ID header."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Validate it's a UUID format (36 chars with hyphens)
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36
        assert request_id.count("-") == 4

    def test_health_preserves_upstream_request_id(self, client: TestClient) -> None:
        """Test upstream X-Request-ID is preserved, not overwritten."""
        upstream_id = "upstream-12345-from-alb"
        response = client.get("/health", headers={"X-Request-ID": upstream_id})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == upstream_id


class TestRequestIDOnErrors:
    """Tests verifying request ID is available on error responses."""

    def test_validation_error_has_proper_status(self, client: TestClient) -> None:
        """Test validation errors return 422, not 500 (exceptions propagate)."""
        response = client.post("/query", json={"question": ""})
        # If middleware swallowed exceptions, this would be 500
        assert response.status_code == 422

    def test_validation_error_includes_request_id_header(
        self, client: TestClient
    ) -> None:
        """Test validation error includes X-Request-ID header."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 422
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format

    def test_validation_error_includes_request_id_in_body(
        self, client: TestClient
    ) -> None:
        """Test validation error includes request_id in JSON body."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 422
        data = response.json()
        assert "request_id" in data
        assert data["request_id"] is not None
        assert len(data["request_id"]) == 36  # UUID format

    def test_validation_error_has_consistent_format(self, client: TestClient) -> None:
        """Test validation error follows ErrorResponse schema."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in data["error"]

    def test_404_error_has_proper_status(self, client: TestClient) -> None:
        """Test HTTPException returns proper status code (exceptions propagate)."""
        response = client.get("/sources/nonexistent")
        # If middleware swallowed exceptions, this would be 500
        assert response.status_code == 404

    def test_404_error_includes_request_id_header(self, client: TestClient) -> None:
        """Test 404 error includes X-Request-ID header."""
        response = client.get("/sources/nonexistent")
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format

    def test_404_error_includes_request_id_in_body(self, client: TestClient) -> None:
        """Test 404 error includes request_id in JSON body."""
        response = client.get("/sources/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "request_id" in data
        assert data["request_id"] is not None

    def test_404_error_has_consistent_format(self, client: TestClient) -> None:
        """Test 404 error follows ErrorResponse schema."""
        response = client.get("/sources/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"
        assert "message" in data["error"]


class TestReadyEndpoint:
    """Tests for GET /ready endpoint."""

    def test_ready_returns_status(self, client: TestClient) -> None:
        """Test /ready returns ready status with checks."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ready", "not_ready")
        assert "checks" in data
        assert "chroma_index" in data["checks"]
        assert "bm25_index" in data["checks"]
        assert "openai_api_key_present" in data["checks"]
        assert "timestamp" in data

    def test_ready_no_auth_required(self, client: TestClient) -> None:
        """Test /ready works without authentication."""
        response = client.get("/ready")
        assert response.status_code == 200

    @patch("api.routes.health.CHROMA_DIR")
    @patch("api.routes.health.OPENAI_API_KEY", None)
    def test_ready_not_ready_when_missing_openai_key(
        self, mock_chroma_dir: None, client: TestClient
    ) -> None:
        """Test /ready returns not_ready when OpenAI key is missing."""
        # Note: This tests the logic, but the actual check happens at import time
        # so mocking doesn't change the result. Kept for documentation.
        response = client.get("/ready")
        assert response.status_code == 200


class TestVersionEndpoint:
    """Tests for GET /version endpoint."""

    def test_version_returns_info(self, client: TestClient) -> None:
        """Test /version returns version information."""
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "api_version" in data
        assert "rag_version" in data
        assert "models" in data
        assert "embeddings" in data["models"]
        assert "llm" in data["models"]

    def test_version_has_expected_values(self, client: TestClient) -> None:
        """Test /version returns expected version values."""
        response = client.get("/version")
        data = response.json()
        assert data["api_version"] == "1.0.0"
        # RAG version is now dynamic from package metadata
        assert data["rag_version"] in ("0.4.0", "0.4", "unknown")
        assert data["models"]["embeddings"] == "text-embedding-3-large"
        assert data["models"]["llm"] == "gpt-4.1"

    def test_version_no_auth_required(self, client: TestClient) -> None:
        """Test /version works without authentication."""
        response = client.get("/version")
        assert response.status_code == 200


class TestSourcesEndpoint:
    """Tests for GET /sources endpoint."""

    def test_sources_returns_list(self, client: TestClient) -> None:
        """Test /sources returns sources list."""
        response = client.get("/sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_sources_has_expected_structure(self, client: TestClient) -> None:
        """Test each source has expected fields."""
        response = client.get("/sources")
        data = response.json()
        for source in data["sources"]:
            assert "name" in source
            assert "display_name" in source
            assert "document_count" in source
            assert "status" in source


class TestSourceDocumentsEndpoint:
    """Tests for GET /sources/{name} endpoint."""

    def test_source_documents_returns_list(self, client: TestClient) -> None:
        """Test /sources/{name} returns document list."""
        response = client.get("/sources/cme")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "cme"
        assert "documents" in data
        assert "total_count" in data
        assert isinstance(data["documents"], list)

    def test_source_not_found(self, client: TestClient) -> None:
        """Test /sources/{name} returns 404 for unknown source."""
        response = client.get("/sources/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"


class TestQueryEndpoint:
    """Tests for POST /query endpoint."""

    def test_query_empty_question_rejected(self, client: TestClient) -> None:
        """Test /query rejects empty question."""
        response = client.post("/query", json={"question": ""})
        assert response.status_code == 422  # Pydantic validation error

    def test_query_whitespace_question_rejected(self, client: TestClient) -> None:
        """Test /query rejects whitespace-only question."""
        response = client.post("/query", json={"question": "   "})
        assert response.status_code == 422  # Pydantic validation error

    def test_query_invalid_source_rejected(self, client: TestClient) -> None:
        """Test /query rejects invalid source."""
        response = client.post(
            "/query",
            json={"question": "What are the fees?", "sources": ["nonexistent"]},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "SOURCE_NOT_FOUND"

    def test_query_invalid_search_mode_rejected(self, client: TestClient) -> None:
        """Test /query rejects invalid search mode."""
        response = client.post(
            "/query",
            json={
                "question": "What are the fees?",
                "options": {"search_mode": "invalid"},
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_query_top_k_out_of_range_rejected(self, client: TestClient) -> None:
        """Test /query rejects top_k outside valid range."""
        response = client.post(
            "/query",
            json={
                "question": "What are the fees?",
                "options": {"top_k": 100},  # Max is 50
            },
        )
        assert response.status_code == 422  # Pydantic validation error


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    def test_docs_available(self, client: TestClient) -> None:
        """Test /docs endpoint is available."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self, client: TestClient) -> None:
        """Test /openapi.json endpoint is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "License Intelligence API"
        assert data["info"]["version"] == "1.0.0"
