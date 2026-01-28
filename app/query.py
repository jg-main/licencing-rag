# app/query.py
"""Query pipeline for the License Intelligence System."""

import sys
from typing import Any

import chromadb
from chromadb.errors import NotFoundError

from app.config import CHROMA_DIR
from app.config import DEFAULT_PROVIDERS
from app.config import EMBEDDING_DIMENSIONS
from app.config import EMBEDDING_MODEL
from app.config import PROVIDERS
from app.config import TOP_K
from app.definitions import format_definitions_for_context
from app.definitions import format_definitions_for_output
from app.definitions import get_definitions_retriever
from app.embed import OpenAIEmbeddingFunction
from app.llm import LLMConnectionError
from app.llm import get_llm
from app.logging import get_logger
from app.normalize import normalize_query
from app.prompts import QA_PROMPT
from app.prompts import QA_PROMPT_NO_DEFINITIONS
from app.prompts import SYSTEM_PROMPT
from app.prompts import get_refusal_message
from app.search import BM25Index
from app.search import HybridSearcher
from app.search import SearchMode

log = get_logger(__name__)


def format_context(
    documents: list[str],
    metadatas: list[dict],
) -> str:
    """Format retrieved documents into context string.

    Args:
        documents: List of document texts.
        metadatas: List of metadata dicts.

    Returns:
        Formatted context string.
    """
    context_parts = []
    for doc, meta in zip(documents, metadatas):
        provider = meta.get("provider", "unknown").upper()
        # Prefer document_path (includes subdirectory) for unambiguous citations
        source = meta.get("document_path") or meta.get("document_name", "Unknown")
        section = meta.get("section_heading", "N/A")
        page_start = meta.get("page_start", "?")
        page_end = meta.get("page_end", "?")

        if page_start == page_end:
            page_info = f"Page {page_start}"
        else:
            page_info = f"Pages {page_start}-{page_end}"

        header = f"--- [{provider}] {source} | {section} | {page_info} ---"
        context_parts.append(f"{header}\n{doc}")

    return "\n\n".join(context_parts)


def query(
    question: str,
    providers: list[str] | None = None,
    top_k: int = TOP_K,
    search_mode: str = "hybrid",
    include_definitions: bool = True,
    debug: bool = False,
) -> dict:
    """Query the knowledge base.

    Args:
        question: User question.
        providers: List of providers to query. Defaults to all configured.
        top_k: Number of chunks to retrieve per provider.
        search_mode: Search mode - "vector", "keyword", or "hybrid" (default).
        include_definitions: If True, auto-link definitions for terms in context.
        debug: If True, include normalization details in response.

    Returns:
        Dictionary with answer, context, citations, definitions, and metadata including:
        - search_mode: The requested search mode
        - effective_search_mode: The actual mode used (may differ if fallback occurred)
        - definitions: List of auto-linked definitions (if include_definitions=True)

    Raises:
        RuntimeError: If no collections are available.
        ValueError: If invalid provider or search mode.
    """
    if providers is None or len(providers) == 0:
        providers = DEFAULT_PROVIDERS

    # Validate providers
    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        log.error(
            "invalid_providers", invalid=invalid, available=list(PROVIDERS.keys())
        )
        raise ValueError(
            f"Unknown providers: {invalid}. Available: {list(PROVIDERS.keys())}"
        )

    # Validate and convert search mode
    try:
        mode = SearchMode(search_mode)
    except ValueError:
        valid_modes = [m.value for m in SearchMode]
        log.error("invalid_search_mode", mode=search_mode, valid=valid_modes)
        raise ValueError(f"Invalid search mode: {search_mode}. Valid: {valid_modes}")

    if not CHROMA_DIR.exists():
        log.error("no_index_found", path=str(CHROMA_DIR))
        raise RuntimeError("No index found. Run 'rag ingest --provider <name>' first.")

    # Normalize query for improved retrieval
    normalized_question = normalize_query(question)
    normalization_failed = False

    # Fall back to original if normalization produces empty string
    if not normalized_question:
        log.warning(
            "normalization_empty",
            original=question,
            message="Normalization produced empty query, using original",
        )
        normalized_question = question
        normalization_failed = True

    log.info(
        "query_started",
        question=question[:100],
        normalized=normalized_question[:100],
        providers=providers,
        top_k=top_k,
        search_mode=search_mode,
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = OpenAIEmbeddingFunction()

    all_documents: list[str] = []
    all_metadatas: list[dict[str, Any]] = []

    # Track actual mode used (may differ from requested due to fallbacks)
    actual_modes_used: set[str] = set()

    for provider in providers:
        collection_name = PROVIDERS[provider].get("collection", f"{provider}_docs")

        try:
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embed_fn,  # type: ignore[arg-type]
            )
            # Verify embedding model and dimensions match (prevent mixed embeddings)
            coll_meta = collection.metadata or {}
            stored_model = coll_meta.get("embedding_model")
            stored_dims = coll_meta.get("embedding_dimensions")

            # Block if metadata is missing (legacy index) or mismatched
            if not stored_model:
                log.error(
                    "embedding_metadata_missing",
                    collection=collection_name,
                    message="Legacy index without embedding metadata",
                )
                raise RuntimeError(
                    f"Index '{collection_name}' is missing embedding metadata. "
                    "This may be a legacy Ollama index. "
                    "Re-ingest with 'rag ingest --provider <name> --force'."
                )

            if stored_model != EMBEDDING_MODEL:
                log.error(
                    "embedding_model_mismatch",
                    collection=collection_name,
                    stored=stored_model,
                    current=EMBEDDING_MODEL,
                )
                raise RuntimeError(
                    f"Embedding model mismatch: index uses '{stored_model}', "
                    f"but current config uses '{EMBEDDING_MODEL}'. "
                    "Re-ingest with 'rag ingest --provider <name> --force'."
                )

            if stored_dims and stored_dims != EMBEDDING_DIMENSIONS:
                log.error(
                    "embedding_dimensions_mismatch",
                    collection=collection_name,
                    stored=stored_dims,
                    current=EMBEDDING_DIMENSIONS,
                )
                raise RuntimeError(
                    f"Embedding dimensions mismatch: index uses {stored_dims}, "
                    f"but current config uses {EMBEDDING_DIMENSIONS}. "
                    "Re-ingest with 'rag ingest --provider <name> --force'."
                )
        except (NotFoundError, ValueError):
            # NotFoundError: ChromaDB >= 1.4.1
            # ValueError: ChromaDB < 1.4.1 (legacy compatibility)
            log.warning(
                "collection_not_found", collection=collection_name, provider=provider
            )
            continue

        # Load BM25 index for hybrid/keyword search
        bm25_index = None
        effective_mode = mode
        if mode in (SearchMode.HYBRID, SearchMode.KEYWORD):
            bm25_index = BM25Index.load(provider)
            if bm25_index is None and mode == SearchMode.KEYWORD:
                log.warning(
                    "bm25_index_missing_fallback",
                    provider=provider,
                    requested_mode="keyword",
                    fallback_mode="vector",
                )
                # Actually fall back to vector mode
                effective_mode = SearchMode.VECTOR

        # Use hybrid searcher for all search modes
        # Use normalized query for better retrieval
        searcher = HybridSearcher(provider, collection, bm25_index)
        search_results = searcher.search(
            normalized_question, mode=effective_mode, top_k=top_k
        )

        # Track the actual mode used
        actual_modes_used.add(effective_mode.value)

        for result in search_results:
            all_documents.append(result.text)
            all_metadatas.append(result.metadata)
            # Track source for debug info
            if debug:
                result.metadata["_retrieval_source"] = result.source

    # Determine effective search mode
    # If fallback occurred or mixed modes, report the actual mode(s) used
    if len(actual_modes_used) == 1:
        effective_search_mode = actual_modes_used.pop()
    elif len(actual_modes_used) > 1:
        # Multiple providers used different modes (rare edge case)
        effective_search_mode = "mixed"
    else:
        # No results retrieved, use requested mode
        effective_search_mode = search_mode

    if not all_documents:
        log.info("no_chunks_retrieved", question=question[:100])
        response = {
            "answer": get_refusal_message(providers),
            "context": "",
            "citations": [],
            "definitions": [],
            "chunks_retrieved": 0,
            "providers": providers,
            "search_mode": search_mode,
            "effective_search_mode": effective_search_mode,
        }
        if debug:
            response["debug_info"] = {
                "normalized_query": normalized_question,
                "original_query": question,
                "retrieval_sources": {},
            }
        return response

    log.debug("chunks_retrieved", count=len(all_documents))

    # Format context
    context = format_context(all_documents, all_metadatas)

    # Auto-link definitions if enabled
    definitions_dict: dict = {}
    definitions_context = ""
    if include_definitions:
        try:
            retriever = get_definitions_retriever(tuple(providers))
            # Find definitions for terms in the question and context
            combined_text = question + " " + context
            definitions_dict = retriever.find_definitions_in_text(
                combined_text,
                max_definitions=10,
            )
            if definitions_dict:
                definitions_context = format_definitions_for_context(definitions_dict)
                log.debug(
                    "definitions_found",
                    terms=list(definitions_dict.keys()),
                    count=len(definitions_dict),
                )
        except Exception as e:
            log.warning("definitions_retrieval_failed", error=str(e))

    # Build prompt with provider context
    provider_label = ", ".join(p.upper() for p in providers)

    # Use appropriate prompt based on whether definitions were found
    if definitions_context:
        prompt = QA_PROMPT.format(
            context=context,
            definitions_section=definitions_context,
            question=question,
            provider=provider_label,
        )
    else:
        prompt = QA_PROMPT_NO_DEFINITIONS.format(
            context=context,
            question=question,
            provider=provider_label,
        )

    # Call LLM
    log.debug("calling_llm")
    try:
        llm = get_llm()
        answer = llm.generate(system=SYSTEM_PROMPT, prompt=prompt)
    except LLMConnectionError as e:
        log.error("llm_connection_failed", error=str(e))
        raise RuntimeError(f"LLM connection failed: {e}") from e

    log.info(
        "query_complete",
        chunks=len(all_documents),
        answer_length=len(answer),
        requested_mode=search_mode,
        effective_mode=effective_search_mode,
    )

    # Extract citations
    citations = []
    seen = set()
    for meta in all_metadatas:
        # Prefer document_path (includes subdirectory) for unambiguous citations
        doc_path = meta.get("document_path") or meta.get("document_name", "Unknown")
        section = meta.get("section_heading", "N/A")
        page_start = meta.get("page_start", "?")
        page_end = meta.get("page_end", page_start)  # Default to start if no end
        provider = meta.get("provider", "unknown")
        # Use document_path in key to prevent same-filename-different-subdirectory collisions
        key = (provider, doc_path, section, page_start, page_end)
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "document": doc_path,
                    "section": section,
                    "page_start": page_start,
                    "page_end": page_end,
                    "provider": meta.get("provider", "unknown"),
                }
            )

    # Format definitions for output
    definitions_output = (
        format_definitions_for_output(definitions_dict) if definitions_dict else []
    )

    response = {
        "answer": answer,
        "context": context,
        "citations": citations,
        "definitions": definitions_output,
        "chunks_retrieved": len(all_documents),
        "providers": providers,
        "search_mode": search_mode,
        "effective_search_mode": effective_search_mode,
    }

    # Add debug information if requested
    if debug:
        response["debug"] = {
            "original_query": question,
            "normalized_query": normalized_question,
            "normalization_applied": question.lower().strip()
            != normalized_question.lower().strip(),
            "normalization_failed": normalization_failed,
        }

    return response


def print_response(result: dict) -> None:
    """Print a formatted response using Rich console output.

    This function delegates to the output module's print_result function.
    Kept for backward compatibility with existing code.

    Args:
        result: Query result dictionary.
    """
    from app.output import OutputFormat
    from app.output import print_result

    print_result(result, OutputFormat.CONSOLE)


def main(question: str) -> None:
    """CLI entrypoint for queries (legacy support).

    Args:
        question: User question.
    """
    result = query(question)
    print_response(result)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python -m app.query 'Your question here'")
