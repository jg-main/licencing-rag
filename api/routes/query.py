# api/routes/query.py
"""Query endpoint for the License Intelligence API."""

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi import Depends

from api.dependencies import authenticate
from api.exceptions import OpenAIError
from api.exceptions import RateLimitError
from api.exceptions import ServiceUnavailableError
from api.exceptions import SourceNotFoundError
from api.exceptions import ValidationError
from api.middleware.rate_limit import check_rate_limit
from api.models import Citation
from api.models import Definition
from api.models import QueryData
from api.models import QueryMetadata
from api.models import QueryRequest
from api.models import QueryResponse
from app.config import SOURCES
from app.query import query as rag_query

logger = logging.getLogger(__name__)

# Import OpenAI exceptions with fallback to prevent import errors during error handling
try:
    from openai import APIError as OpenAIAPIError
    from openai import APITimeoutError
    from openai import AuthenticationError
    from openai import RateLimitError as OpenAIRateLimitError

    OPENAI_EXCEPTIONS: tuple[type[Exception], ...] = (
        OpenAIAPIError,
        APITimeoutError,
        AuthenticationError,
    )
    OPENAI_RATE_LIMIT_EXCEPTION: type[Exception] | None = OpenAIRateLimitError
except ImportError as import_error:
    # Fallback if OpenAI client changes import paths
    # Log warning so we know the classifier is disabled
    logger.warning(
        "Failed to import OpenAI exception classes. "
        "OpenAI errors will be classified as ServiceUnavailableError (503). "
        "Error: %s",
        import_error,
    )
    OPENAI_EXCEPTIONS = ()
    OPENAI_RATE_LIMIT_EXCEPTION = None

# Apply authentication and rate limiting to all routes in this router
router = APIRouter(
    tags=["Query"], dependencies=[Depends(authenticate), Depends(check_rate_limit)]
)


def _extract_citations(response: dict[str, Any]) -> list[Citation]:
    """Extract citations from RAG response.

    Args:
        response: Raw response from app.query.query().

    Returns:
        List of Citation objects.
    """
    citations: list[Citation] = []

    # Try to get citations from the response
    raw_citations = response.get("citations", [])
    if not raw_citations:
        # Fall back to extracting from supporting_clauses if present
        raw_citations = response.get("supporting_clauses", [])

    for cite in raw_citations:
        # Handle different citation formats
        if isinstance(cite, dict):
            source_info = cite.get("source", {})
            if isinstance(source_info, dict):
                citations.append(
                    Citation(
                        source=source_info.get("source", "unknown"),
                        document=source_info.get("document", "unknown"),
                        section=source_info.get("section"),
                        page=source_info.get("page_start"),
                    )
                )
            else:
                # Flat citation format
                citations.append(
                    Citation(
                        source=cite.get("source", "unknown"),
                        document=cite.get("document", "unknown"),
                        section=cite.get("section"),
                        page=cite.get("page"),
                    )
                )

    return citations


def _extract_definitions(response: dict[str, Any]) -> list[Definition]:
    """Extract definitions from RAG response.

    Args:
        response: Raw response from app.query.query().

    Returns:
        List of Definition objects.
    """
    definitions: list[Definition] = []

    raw_definitions = response.get("definitions", [])
    for defn in raw_definitions:
        if isinstance(defn, dict):
            source_info = defn.get("source", {})
            definitions.append(
                Definition(
                    term=defn.get("term", ""),
                    definition=defn.get("definition", ""),
                    source=Citation(
                        source=source_info.get("source", "unknown"),
                        document=source_info.get("document", "unknown"),
                        section=source_info.get("section"),
                        page=source_info.get("page_start"),
                    ),
                )
            )

    return definitions


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
) -> QueryResponse:
    """Query the licensing knowledge base.

    Executes a RAG query against the configured sources and returns
    an answer with citations.

    Requires authentication via Bearer token in Authorization header.

    Args:
        request: Query request with question and options.
        auth: Authentication context (injected dependency).

    Returns:
        Query response with answer, citations, and metadata.

    Raises:
        UnauthorizedError: If authentication fails (401).
        SourceNotFoundError: If unknown sources are specified.
        ValidationError: For other validation errors.
        ServiceUnavailableError: If index is not found.
        OpenAIError: If OpenAI API call fails.
    """
    start_time = time.time()
    query_id = str(uuid.uuid4())

    # Note: Empty/whitespace questions are validated by Pydantic field validator
    # in QueryRequest model, so no manual check needed here

    # Validate sources if provided
    if request.sources:
        invalid_sources = [s for s in request.sources if s not in SOURCES]
        if invalid_sources:
            raise SourceNotFoundError(
                source=invalid_sources,
                available_sources=list(SOURCES.keys()),
            )

    try:
        # Call the RAG query function
        response = rag_query(
            question=request.question,
            sources=request.sources,
            top_k=request.options.top_k,
            search_mode=request.options.search_mode,
            include_definitions=request.options.include_definitions,
            enable_reranking=request.options.enable_reranking,
            enable_confidence_gate=request.options.enable_confidence_gate,
            debug=False,  # API doesn't expose debug mode
            log_to_console=False,
        )
    except ValueError as e:
        # Invalid parameters (search mode, sources)
        raise ValidationError(message=str(e))
    except RuntimeError as e:
        # Index not found or embedding mismatch
        error_message = str(e)
        if "index" in error_message.lower() or "chroma" in error_message.lower():
            raise ServiceUnavailableError(message=error_message)
        raise ServiceUnavailableError(message=f"RAG system error: {error_message}")
    except Exception as e:
        # Check for OpenAI-specific exceptions by type
        # Handle rate limit errors separately (429) from other OpenAI errors (502)
        if OPENAI_RATE_LIMIT_EXCEPTION and isinstance(e, OPENAI_RATE_LIMIT_EXCEPTION):
            # OpenAI rate limit should surface as 429 for proper client backoff
            # Note: retry_after is included in JSON body; Retry-After header
            # will be added globally in Phase 5 (rate limiting middleware)
            raise RateLimitError(
                message="OpenAI API rate limit exceeded",
                retry_after=getattr(e, "retry_after", None),
            )
        elif OPENAI_EXCEPTIONS and isinstance(e, OPENAI_EXCEPTIONS):
            # Other OpenAI errors (auth, timeout, API errors) are 502 Bad Gateway
            raise OpenAIError(message=str(e))

        # Re-raise as ServiceUnavailableError for other unexpected errors
        raise ServiceUnavailableError(
            message=f"Unexpected error: {str(e)}",
            details={"error_type": type(e).__name__},
        )

    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)

    # Extract structured data from response
    citations = _extract_citations(response)
    definitions = (
        _extract_definitions(response) if request.options.include_definitions else []
    )

    # Determine if query was refused
    refused = response.get("refused", False)
    refusal_reason = response.get("refusal_reason")

    # If not explicitly marked, check for refusal indicators in answer
    answer = response.get("answer", "")
    if not refused and response.get("chunks_retrieved", 0) == 0:
        refused = True
        refusal_reason = "no_chunks_retrieved"

    # Build metadata
    metadata = QueryMetadata(
        query_id=query_id,
        sources_queried=request.sources or list(SOURCES.keys()),
        chunks_retrieved=response.get("chunks_retrieved", 0),
        chunks_used=response.get("chunks_used", response.get("chunks_retrieved", 0)),
        tokens_input=response.get("tokens_input", 0),
        tokens_output=response.get("tokens_output", 0),
        latency_ms=latency_ms,
        refused=refused,
        refusal_reason=refusal_reason if refused else None,
    )

    # Build response
    return QueryResponse(
        success=True,
        data=QueryData(
            answer=answer,
            citations=citations,
            definitions=definitions,
            metadata=metadata,
        ),
    )
