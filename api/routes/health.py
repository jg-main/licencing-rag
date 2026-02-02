# api/routes/health.py
"""Health and status endpoints for the License Intelligence API."""

from datetime import datetime
from datetime import timezone

from fastapi import APIRouter

from api.config import API_VERSION
from api.models import HealthResponse
from api.models import ModelsInfo
from api.models import ReadyChecks
from api.models import ReadyResponse
from api.models import VersionResponse
from app.config import CHROMA_DIR
from app.config import EMBEDDING_MODEL
from app.config import LLM_MODEL
from app.config import OPENAI_API_KEY
from app.search import BM25_INDEX_DIR

router = APIRouter(tags=["Health"])


def _get_rag_version() -> str:
    """Get RAG version from package metadata.

    Reads version from pyproject.toml via importlib.metadata.
    Falls back to 'unknown' if not available.
    """
    try:
        from importlib.metadata import version

        return version("licencing-rag")
    except Exception:
        return "unknown"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Basic liveness check.

    Use for load balancer health checks. Returns immediately without
    checking dependencies.

    Returns:
        Health status with timestamp.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse:
    """Readiness check for service availability.

    Verifies that required indexes and configuration are present.
    Does NOT make live OpenAI API calls to avoid flapping and cost.

    Returns:
        Ready status with individual check results.
    """
    # Check ChromaDB index exists
    chroma_exists = CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())

    # Check BM25 index exists (at least one source has an index)
    bm25_exists = (
        BM25_INDEX_DIR.exists()
        and any(f.suffix == ".pkl" for f in BM25_INDEX_DIR.iterdir())
        if BM25_INDEX_DIR.exists()
        else False
    )

    # Check OpenAI API key is configured (presence only, no validation)
    openai_key_present = bool(OPENAI_API_KEY)

    checks = ReadyChecks(
        chroma_index=chroma_exists,
        bm25_index=bm25_exists,
        openai_api_key_present=openai_key_present,
    )

    # System is ready if all critical checks pass
    all_ready = checks.chroma_index and checks.openai_api_key_present
    # Note: BM25 is optional (vector-only mode still works)

    return ReadyResponse(
        status="ready" if all_ready else "not_ready",
        checks=checks,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """Get API and system version information.

    Returns:
        Version info for API, RAG system, and configured models.
    """
    return VersionResponse(
        api_version=API_VERSION,
        rag_version=_get_rag_version(),
        models=ModelsInfo(
            embeddings=EMBEDDING_MODEL,
            llm=LLM_MODEL,
        ),
    )
