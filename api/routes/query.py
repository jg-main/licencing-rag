# api/routes/query.py
"""Query endpoint for the License Intelligence API."""

import time
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException

from api.models import Citation
from api.models import Definition
from api.models import QueryData
from api.models import QueryMetadata
from api.models import QueryRequest
from api.models import QueryResponse
from app.config import SOURCES
from app.query import query as rag_query

router = APIRouter(tags=["Query"])


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
async def query(request: QueryRequest) -> QueryResponse:
    """Query the licensing knowledge base.

    Executes a RAG query against the configured sources and returns
    an answer with citations.

    Args:
        request: Query request with question and options.

    Returns:
        Query response with answer, citations, and metadata.

    Raises:
        HTTPException: 400 for validation errors, 404 for unknown sources.
    """
    start_time = time.time()
    query_id = str(uuid.uuid4())

    # Validate sources if provided
    if request.sources:
        invalid_sources = [s for s in request.sources if s not in SOURCES]
        if invalid_sources:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "SOURCE_NOT_FOUND",
                    "message": f"Unknown sources: {invalid_sources}",
                    "details": {"available_sources": list(SOURCES.keys())},
                },
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
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e),
            },
        )
    except RuntimeError as e:
        # Index not found or embedding mismatch
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": str(e),
            },
        )
    except Exception as e:
        # Catch OpenAI errors or unexpected failures
        error_message = str(e)
        if "openai" in error_message.lower() or "api" in error_message.lower():
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "OPENAI_ERROR",
                    "message": f"OpenAI API error: {error_message}",
                },
            )
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": f"Unexpected error: {error_message}",
            },
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
