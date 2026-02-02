# api/models/requests.py
"""Pydantic request models for the License Intelligence API."""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class QueryOptions(BaseModel):
    """Optional parameters for query execution."""

    search_mode: Literal["vector", "keyword", "hybrid"] = Field(
        default="hybrid",
        description="Search mode: 'vector' (semantic), 'keyword' (BM25), or 'hybrid' (both)",
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of chunks to retrieve (1-50)",
    )
    enable_reranking: bool = Field(
        default=True,
        description="Enable LLM reranking of retrieved chunks",
    )
    enable_confidence_gate: bool = Field(
        default=True,
        description="Enable confidence gating (refuse if evidence is weak)",
    )
    include_definitions: bool = Field(
        default=False,
        description="Include auto-linked definitions in response",
    )


class QueryRequest(BaseModel):
    """Request body for POST /query endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to ask about licensing documents",
    )
    sources: list[str] | None = Field(
        default=None,
        description="List of sources to query (e.g., ['cme']). Defaults to all.",
    )
    options: QueryOptions = Field(
        default_factory=QueryOptions,
        description="Optional query parameters",
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        """Validate question is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Question cannot be empty or whitespace-only")
        return v.strip()

    @field_validator("sources")
    @classmethod
    def sources_not_empty_list(cls, v: list[str] | None) -> list[str] | None:
        """Validate sources list is not empty if provided."""
        if v is not None and len(v) == 0:
            return None  # Treat empty list as "all sources"
        return v
