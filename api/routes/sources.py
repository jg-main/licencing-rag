# api/routes/sources.py
"""Source management endpoints for the License Intelligence API."""

from fastapi import APIRouter

from api.exceptions import SourceNotFoundError
from api.models import SourceDocumentsResponse
from api.models import SourceInfo
from api.models import SourcesResponse
from app.config import SOURCES
from app.ingest import list_indexed_documents

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=SourcesResponse)
async def list_sources() -> SourcesResponse:
    """List all configured data sources.

    Returns information about each source including document count
    and whether it's currently active (has indexed documents).

    Returns:
        List of sources with metadata.
    """
    sources_list: list[SourceInfo] = []

    for source_key, source_config in SOURCES.items():
        # Get indexed documents for this source
        documents = list_indexed_documents(source_key)
        doc_count = len(documents)

        # Determine status based on whether documents are indexed
        status = "active" if doc_count > 0 else "planned"

        sources_list.append(
            SourceInfo(
                name=source_key,
                display_name=source_config.get("name", source_key.upper()),
                document_count=doc_count,
                status=status,
            )
        )

    return SourcesResponse(sources=sources_list)


@router.get("/{name}", response_model=SourceDocumentsResponse)
async def get_source_documents(name: str) -> SourceDocumentsResponse:
    """List all indexed documents for a specific source.

    Args:
        name: Source identifier (e.g., 'cme').

    Returns:
        List of document paths indexed for the source.

    Raises:
        SourceNotFoundError: If source not found.
    """
    # Validate source exists in configuration
    if name not in SOURCES:
        raise SourceNotFoundError(
            source=name,
            available_sources=list(SOURCES.keys()),
        )

    # Get indexed documents
    documents = list_indexed_documents(name)

    return SourceDocumentsResponse(
        source=name,
        documents=documents,
        total_count=len(documents),
    )
