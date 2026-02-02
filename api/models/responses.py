# api/models/responses.py
"""Pydantic response models for the License Intelligence API."""

from datetime import datetime
from datetime import timezone
from typing import Any

from pydantic import BaseModel
from pydantic import Field

# =============================================================================
# Health & Status Responses
# =============================================================================


class HealthResponse(BaseModel):
    """Response for GET /health endpoint."""

    status: str = Field(default="healthy", description="Health status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server time (UTC)",
    )


class ReadyChecks(BaseModel):
    """Individual readiness checks."""

    chroma_index: bool = Field(description="ChromaDB index exists and is accessible")
    bm25_index: bool = Field(description="BM25 keyword index exists")
    openai_api_key_present: bool = Field(description="OpenAI API key is configured")


class ReadyResponse(BaseModel):
    """Response for GET /ready endpoint."""

    status: str = Field(description="Ready status: 'ready' or 'not_ready'")
    checks: ReadyChecks = Field(description="Individual readiness check results")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Current server time (UTC)",
    )


class ModelsInfo(BaseModel):
    """Model configuration information."""

    embeddings: str = Field(description="Embedding model name")
    llm: str = Field(description="LLM model name")


class VersionResponse(BaseModel):
    """Response for GET /version endpoint."""

    api_version: str = Field(description="API version")
    rag_version: str = Field(description="RAG system version")
    models: ModelsInfo = Field(description="Configured models")


# =============================================================================
# Query Responses
# =============================================================================


class Citation(BaseModel):
    """A citation referencing a source document."""

    source: str = Field(description="Source provider (e.g., 'cme')")
    document: str = Field(description="Document path or filename")
    section: str | None = Field(
        default=None, description="Section heading if available"
    )
    page: int | None = Field(default=None, description="Page number if available")


class Definition(BaseModel):
    """An auto-linked definition."""

    term: str = Field(description="The defined term")
    definition: str = Field(description="The definition text")
    source: Citation = Field(description="Source of the definition")


class QueryMetadata(BaseModel):
    """Metadata about query execution."""

    query_id: str = Field(description="Unique query identifier (UUID)")
    sources_queried: list[str] = Field(description="Sources that were queried")
    chunks_retrieved: int = Field(description="Number of chunks retrieved")
    chunks_used: int = Field(description="Number of chunks used in context")
    tokens_input: int = Field(default=0, description="Input tokens consumed")
    tokens_output: int = Field(default=0, description="Output tokens generated")
    latency_ms: int = Field(description="Query latency in milliseconds")
    refused: bool = Field(default=False, description="Whether query was refused")
    refusal_reason: str | None = Field(
        default=None, description="Reason for refusal if refused"
    )


class QueryData(BaseModel):
    """Successful query response data."""

    answer: str = Field(description="The generated answer")
    citations: list[Citation] = Field(
        default_factory=list, description="Supporting citations"
    )
    definitions: list[Definition] = Field(
        default_factory=list, description="Auto-linked definitions"
    )
    metadata: QueryMetadata = Field(description="Query execution metadata")


class QueryResponse(BaseModel):
    """Response for POST /query endpoint."""

    success: bool = Field(default=True, description="Whether request succeeded")
    data: QueryData = Field(description="Query result data")


# =============================================================================
# Sources Responses
# =============================================================================


class SourceInfo(BaseModel):
    """Information about a data source."""

    name: str = Field(description="Source identifier (e.g., 'cme')")
    display_name: str = Field(description="Human-readable source name")
    document_count: int = Field(description="Number of indexed documents")
    status: str = Field(description="Source status: 'active' or 'planned'")


class SourcesResponse(BaseModel):
    """Response for GET /sources endpoint."""

    sources: list[SourceInfo] = Field(description="List of available sources")


class SourceDocumentsResponse(BaseModel):
    """Response for GET /sources/{name} endpoint."""

    source: str = Field(description="Source identifier")
    documents: list[str] = Field(description="List of indexed document paths")
    total_count: int = Field(description="Total number of documents")


# =============================================================================
# Error Responses
# =============================================================================


class ErrorDetails(BaseModel):
    """Additional error context."""

    field: str | None = Field(default=None, description="Field that caused the error")
    reason: str | None = Field(default=None, description="Detailed reason")
    extra: dict[str, Any] | None = Field(default=None, description="Additional context")


class ErrorInfo(BaseModel):
    """Error information."""

    code: str = Field(description="Error code (e.g., 'VALIDATION_ERROR')")
    message: str = Field(description="Human-readable error message")
    details: ErrorDetails | None = Field(
        default=None, description="Additional error details"
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""

    success: bool = Field(default=False, description="Always false for errors")
    error: ErrorInfo = Field(description="Error information")
    request_id: str | None = Field(default=None, description="Request ID for tracing")
