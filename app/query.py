# app/query.py
"""Query pipeline for the License Intelligence System."""

import sys
from typing import Any

import chromadb
from chromadb.errors import NotFoundError

from app.config import CHROMA_DIR
from app.config import CONFIDENCE_GATE_ENABLED
from app.config import CONTEXT_BUDGET_ENABLED
from app.config import DEFAULT_SOURCES
from app.config import EMBEDDING_DIMENSIONS
from app.config import EMBEDDING_MODEL
from app.config import MIN_CHUNKS_REQUIRED
from app.config import RELEVANCE_THRESHOLD
from app.config import RERANKING_ENABLED
from app.config import SOURCES
from app.config import TOP_K
from app.debug import build_debug_output
from app.debug import format_retrieval_info
from app.debug import write_debug_output
from app.definitions import format_definitions_for_context
from app.definitions import format_definitions_for_output
from app.definitions import get_definitions_retriever
from app.embed import OpenAIEmbeddingFunction
from app.gate import get_refusal_reason_message
from app.gate import should_refuse
from app.llm import LLMConnectionError
from app.llm import get_llm
from app.logging import get_logger
from app.normalize import normalize_query
from app.prompts import QA_PROMPT
from app.prompts import QA_PROMPT_NO_DEFINITIONS
from app.prompts import SYSTEM_PROMPT
from app.prompts import get_refusal_message
from app.rerank import rerank_chunks
from app.search import BM25Index
from app.search import HybridSearcher
from app.search import SearchMode
from app.validate import get_stricter_system_prompt
from app.validate import validate_llm_output

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
        source_name = meta.get("source", meta.get("provider", "unknown")).upper()
        # Prefer document_path (includes subdirectory) for unambiguous citations
        doc_path = meta.get("document_path") or meta.get("document_name", "Unknown")
        section = meta.get("section_heading", "N/A")
        page_start = meta.get("page_start", "?")
        page_end = meta.get("page_end", "?")

        if page_start == page_end:
            page_info = f"Page {page_start}"
        else:
            page_info = f"Pages {page_start}-{page_end}"

        header = f"--- [{source_name}] {doc_path} | {section} | {page_info} ---"
        context_parts.append(f"{header}\n{doc}")

    return "\n\n".join(context_parts)


def query(
    question: str,
    sources: list[str] | None = None,
    top_k: int = TOP_K,
    search_mode: str = "hybrid",
    include_definitions: bool = True,
    enable_reranking: bool = RERANKING_ENABLED,
    enable_budget: bool = CONTEXT_BUDGET_ENABLED,
    enable_confidence_gate: bool = CONFIDENCE_GATE_ENABLED,
    debug: bool = False,
    log_to_console: bool = False,
) -> dict:
    """Query the knowledge base.

    Args:
        question: User question.
        sources: List of sources to query. Defaults to all configured.
        top_k: Number of chunks to retrieve per source.
        search_mode: Search mode - "vector", "keyword", or "hybrid" (default).
        include_definitions: If True, auto-link definitions for terms in context.
        enable_reranking: If True, use LLM to rerank chunks (Phase 4).
        enable_budget: If True, enforce token budget on context (Phase 5).
        enable_confidence_gate: If True, refuse on low confidence (Phase 6).
        debug: If True, include normalization details in response.
        log_to_console: If True, write audit log to console (stderr).

    Returns:
        Dictionary with answer, context, citations, definitions, and metadata including:
        - search_mode: The requested search mode
        - effective_search_mode: The actual mode used (may differ if fallback occurred)
        - definitions: List of auto-linked definitions (if include_definitions=True)

    Raises:
        RuntimeError: If no collections are available.
        ValueError: If invalid source or search mode.
    """
    import time

    start_time = time.time()  # Track query latency for audit logging

    if sources is None or len(sources) == 0:
        sources = DEFAULT_SOURCES

    # Validate sources
    invalid = [p for p in sources if p not in SOURCES]
    if invalid:
        log.error("invalid_sources", invalid=invalid, available=list(SOURCES.keys()))
        raise ValueError(
            f"Unknown sources: {invalid}. Available: {list(SOURCES.keys())}"
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
        raise RuntimeError("No index found. Run 'rag ingest --source <name>' first.")

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
        sources=sources,
        top_k=top_k,
        search_mode=search_mode,
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = OpenAIEmbeddingFunction()

    all_search_results: list[dict[str, Any]] = []

    # Track actual mode used (may differ from requested due to fallbacks)
    actual_modes_used: set[str] = set()

    for source in sources:
        collection_name = SOURCES[source].get("collection", f"{source}_docs")

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
                    "Re-ingest with 'rag ingest --source <name> --force'."
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
                    "Re-ingest with 'rag ingest --source <name> --force'."
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
                    "Re-ingest with 'rag ingest --source <name> --force'."
                )
        except (NotFoundError, ValueError):
            # NotFoundError: ChromaDB >= 1.4.1
            # ValueError: ChromaDB < 1.4.1 (legacy compatibility)
            log.warning(
                "collection_not_found", collection=collection_name, source=source
            )
            continue

        # Load BM25 index for hybrid/keyword search
        bm25_index = None
        effective_mode = mode
        if mode in (SearchMode.HYBRID, SearchMode.KEYWORD):
            bm25_index = BM25Index.load(source)
            if bm25_index is None and mode == SearchMode.KEYWORD:
                log.warning(
                    "bm25_index_missing_fallback",
                    source=source,
                    requested_mode="keyword",
                    fallback_mode="vector",
                )
                # Actually fall back to vector mode
                effective_mode = SearchMode.VECTOR

        # Use hybrid searcher for all search modes
        # Use normalized query for better retrieval
        searcher = HybridSearcher(source, collection, bm25_index)
        search_results = searcher.search(
            normalized_question, mode=effective_mode, top_k=top_k
        )

        # Track the actual mode used
        actual_modes_used.add(effective_mode.value)

        # Store search results with all metadata for potential reranking
        for result in search_results:
            search_result_dict = {
                "chunk_id": result.chunk_id,
                "text": result.text,
                "metadata": result.metadata,
                "score": result.score,
                "source": source,  # Provider source (cme, opra, etc.)
                "method": result.source,  # Search method (vector, keyword, hybrid)
            }
            all_search_results.append(search_result_dict)

    # Determine effective search mode
    # If fallback occurred or mixed modes, report the actual mode(s) used
    if len(actual_modes_used) == 1:
        effective_search_mode = actual_modes_used.pop()
    elif len(actual_modes_used) > 1:
        # Multiple sources used different modes (rare edge case)
        effective_search_mode = "mixed"
    else:
        # No results retrieved, use requested mode
        effective_search_mode = search_mode

    if not all_search_results:
        log.info("no_chunks_retrieved", question=question[:100])
        response = {
            "answer": get_refusal_message(sources),
            "context": "",
            "citations": [],
            "definitions": [],
            "chunks_retrieved": 0,
            "sources": sources,
            "search_mode": search_mode,
            "effective_search_mode": effective_search_mode,
        }
        if debug:
            # Use format_retrieval_info for rich debug output with scores/ranks
            retrieval_info = format_retrieval_info(all_search_results, sources)

            debug_dict = build_debug_output(
                original_query=question,
                normalized_query=normalized_question,
                normalization_applied=(
                    question.lower().strip() != normalized_question.lower().strip()
                ),
                normalization_failed=normalization_failed,
                sources=sources,
                search_mode=search_mode,
                effective_search_mode=effective_search_mode,
                retrieval_info=retrieval_info,
                final_chunks_count=0,
                final_context_tokens=0,
                definitions_count=0,
                llm_called=False,
            )
            response["debug"] = debug_dict

            # Always write debug output (stderr always, file if DEBUG_LOG_ENABLED=True)
            write_debug_output(debug_dict, write_to_stderr=True)

        # Audit logging (always-on for compliance)
        from app.audit import calculate_latency_ms
        from app.audit import log_query_response

        log_query_response(
            query=question,
            answer=str(response["answer"]),
            sources=sources,
            chunks_retrieved=0,
            chunks_used=0,
            tokens_input=0,
            tokens_output=0,
            latency_ms=calculate_latency_ms(start_time),
            refused=True,
            refusal_reason="no_chunks_retrieved",
            write_to_console=log_to_console,
        )

        return response

    log.debug("chunks_retrieved", count=len(all_search_results))

    # Phase 4: LLM Reranking (optional)
    rerank_info: dict[str, Any] = {}
    kept_chunks: list[Any] = []  # Initialize to avoid unbound variable
    dropped_chunks: list[Any] = []  # Initialize to avoid unbound variable
    fallback_triggered = False  # Track if reranking fallback was used

    if enable_reranking:
        log.info("reranking_started", chunk_count=len(all_search_results))
        kept_chunks, dropped_chunks = rerank_chunks(
            chunks=all_search_results,
            question=question,
            # Uses MIN_RERANKING_SCORE and MAX_CHUNKS_AFTER_RERANKING from config
        )

        # CRITICAL: If reranking dropped all chunks, fall back to original ranking
        # This prevents false refusals when reranker is overly strict (accuracy > cost)
        if not kept_chunks:
            from app.config import MAX_CHUNKS_AFTER_RERANKING
            from app.config import RERANKING_INCLUDE_EXPLANATIONS

            log.warning(
                "reranking_dropped_all_chunks_fallback",
                question=question,
                total_chunks=len(all_search_results),
                action="falling back to original ranking",
            )
            # Sort by original relevance score (desc) before capping to preserve quality
            sorted_results: list[dict[str, Any]] = sorted(
                all_search_results, key=lambda x: x["score"], reverse=True
            )
            fallback_results = sorted_results[:MAX_CHUNKS_AFTER_RERANKING]
            all_documents = [r["text"] for r in fallback_results]
            all_metadatas = [r["metadata"] for r in fallback_results]

            # Set original retrieval scores for budget prioritization in fallback case
            for i, fallback_result in enumerate(fallback_results):
                all_metadatas[i]["_relevance_score"] = fallback_result["score"]
                all_metadatas[i]["_retrieval_source"] = fallback_result["source"]

            # Mark fallback as triggered (scores are retrieval, not reranked)
            fallback_triggered = True

            # Track fallback in debug info (only if debug mode is on)
            if debug:
                rerank_info = {
                    "enabled": True,
                    "fallback_triggered": True,
                    "chunks_before_reranking": len(all_search_results),
                    "chunks_after_reranking": len(fallback_results),
                    "dropped_chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "relevance_score": chunk.relevance_score,
                            # Only include explanation if requested
                            **(
                                {"explanation": chunk.explanation}
                                if RERANKING_INCLUDE_EXPLANATIONS
                                else {}
                            ),
                        }
                        for chunk in dropped_chunks
                    ],
                }
            else:
                rerank_info = {"enabled": True, "fallback_triggered": True}
        else:
            # Use reranked chunks for context
            all_documents = [chunk.text for chunk in kept_chunks]
            all_metadatas = [chunk.metadata for chunk in kept_chunks]

            # Set relevance scores for budget prioritization
            for i, chunk in enumerate(kept_chunks):
                all_metadatas[i]["_relevance_score"] = chunk.relevance_score
                all_metadatas[i]["_retrieval_source"] = chunk.source

            # No fallback - using reranked scores
            fallback_triggered = False

            # Track reranking info for debug mode (only if not fallback)
            if debug:
                from app.config import RERANKING_INCLUDE_EXPLANATIONS

                rerank_info = {
                    "enabled": True,
                    "fallback_triggered": False,
                    "chunks_before_reranking": len(all_search_results),
                    "chunks_after_reranking": len(kept_chunks),
                    "kept_chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "relevance_score": chunk.relevance_score,
                            "original_score": chunk.original_score,
                            "source": chunk.source,
                            # Only include explanation if explanations were requested
                            **(
                                {"explanation": chunk.explanation}
                                if RERANKING_INCLUDE_EXPLANATIONS
                                else {}
                            ),
                        }
                        for chunk in kept_chunks
                    ],
                    "dropped_chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "relevance_score": chunk.relevance_score,
                            # Only include explanation if explanations were requested
                            **(
                                {"explanation": chunk.explanation}
                                if RERANKING_INCLUDE_EXPLANATIONS
                                else {}
                            ),
                        }
                        for chunk in dropped_chunks
                    ],
                }

        log.info(
            "reranking_complete",
            kept=len(all_documents),  # Use all_documents to reflect fallback
            dropped=len(dropped_chunks),
            top_scores=[c.relevance_score for c in kept_chunks] if kept_chunks else [],
        )
    else:
        # No reranking - use all retrieved chunks
        all_documents = [r["text"] for r in all_search_results]
        all_metadatas = [r["metadata"] for r in all_search_results]

        # Store original retrieval scores for budget prioritization when reranking disabled
        for i, search_result in enumerate(all_search_results):
            all_metadatas[i]["_relevance_score"] = search_result["score"]

        # Track retrieval source for debug info
        if debug:
            for i, search_result in enumerate(all_search_results):
                all_metadatas[i]["_retrieval_source"] = search_result["source"]

        rerank_info = {"enabled": False}

    # Compute scores_are_reranked flag once (accuracy-first, explicit)
    # True only if: reranking enabled AND produced chunks AND no fallback occurred
    scores_are_reranked = (
        enable_reranking and bool(kept_chunks) and not fallback_triggered
    )

    # Phase 6: Confidence Gating (apply after reranking, before budget/LLM)
    gate_info: dict[str, Any] = {}
    if enable_confidence_gate:
        from app.config import RETRIEVAL_MIN_RATIO
        from app.config import RETRIEVAL_MIN_SCORE

        # Build chunk objects for gating (need relevance scores)
        gate_chunks = []
        for _i, (_doc, meta) in enumerate(zip(all_documents, all_metadatas)):
            # Create a simple object with relevance_score
            class ChunkForGating:
                def __init__(self, score: float):
                    self.relevance_score = score

            score = meta.get("_relevance_score", 0)
            gate_chunks.append(ChunkForGating(score))

        refuse, refusal_reason = should_refuse(
            gate_chunks,
            scores_are_reranked=scores_are_reranked,
            relevance_threshold=RELEVANCE_THRESHOLD,
            min_chunks=MIN_CHUNKS_REQUIRED,
            retrieval_min_score=RETRIEVAL_MIN_SCORE,
            retrieval_min_ratio=RETRIEVAL_MIN_RATIO,
        )

        gate_info = {
            "enabled": True,
            "scores_are_reranked": scores_are_reranked,
            "threshold": RELEVANCE_THRESHOLD if scores_are_reranked else None,
            "min_chunks_required": MIN_CHUNKS_REQUIRED if scores_are_reranked else None,
            "retrieval_min_score": RETRIEVAL_MIN_SCORE
            if not scores_are_reranked
            else None,
            "retrieval_min_ratio": RETRIEVAL_MIN_RATIO
            if not scores_are_reranked
            else None,
            "refused": refuse,
            "refusal_reason": refusal_reason,
        }

        if refuse:
            # Code-enforced refusal - skip LLM call entirely
            log.warning(
                "confidence_gate_refused",
                reason=refusal_reason,
                chunk_count=len(gate_chunks),
            )

            refusal_message = get_refusal_message(sources)
            reason_detail = get_refusal_reason_message(refusal_reason)

            response = {
                "answer": refusal_message,
                "context": "",
                "citations": [],
                "definitions": [],
                "chunks_retrieved": len(all_documents),
                "sources": sources,
                "search_mode": search_mode,
                "effective_search_mode": effective_search_mode,
                "refused": True,
                "refusal_reason": refusal_reason,
                "refusal_detail": reason_detail,
            }

            if debug:
                retrieval_info = format_retrieval_info(all_search_results, sources)

                # Build comprehensive debug for confidence gate refusal
                debug_dict = build_debug_output(
                    original_query=question,
                    normalized_query=normalized_question,
                    normalization_applied=(
                        question.lower().strip() != normalized_question.lower().strip()
                    ),
                    normalization_failed=normalization_failed,
                    sources=sources,
                    search_mode=search_mode,
                    effective_search_mode=effective_search_mode,
                    retrieval_info=retrieval_info,
                    reranking_info=rerank_info if rerank_info else None,
                    confidence_gate_info=gate_info,
                    final_chunks_count=len(all_documents),
                    final_context_tokens=0,  # No context built if refused
                    definitions_count=0,
                    llm_called=False,
                    validation_info={"refusal": True, "reason": refusal_reason},
                )
                response["debug"] = debug_dict

                # Always write debug output when debug=True (stderr always, file if enabled)
                write_debug_output(debug_dict, write_to_stderr=True)

            # Audit logging (always-on for compliance)
            from app.audit import calculate_latency_ms
            from app.audit import log_query_response

            log_query_response(
                query=question,
                answer=str(response["answer"]),
                sources=sources,
                chunks_retrieved=len(all_documents),
                chunks_used=0,
                tokens_input=0,
                tokens_output=0,
                latency_ms=calculate_latency_ms(start_time),
                refused=True,
                refusal_reason=refusal_reason,
                write_to_console=log_to_console,
            )

            return response

        log.info("confidence_gate_passed", chunk_count=len(gate_chunks))
    else:
        gate_info = {"enabled": False}

    # Phase 5: Full-Prompt Budget Enforcement (apply after reranking)
    budget_info: dict[str, Any] = {}
    if enable_budget:
        from app.budget import enforce_full_prompt_budget
        from app.config import MAX_CONTEXT_TOKENS

        # Prepare chunks with metadata including relevance scores
        chunks_with_metadata = list(zip(all_documents, all_metadatas))

        # Build source label
        source_label = ", ".join(p.upper() for p in sources)

        # First pass: enforce budget WITHOUT definitions to get final chunks
        # This prevents definitions from terms in dropped chunks
        kept_chunks_after_budget, budget_info = enforce_full_prompt_budget(
            chunks=chunks_with_metadata,
            system_prompt=SYSTEM_PROMPT,
            question=question,
            definitions_context="",  # No definitions yet
            provider_label=source_label,
            max_tokens=MAX_CONTEXT_TOKENS,
        )

        # Update documents and metadata with budget-enforced chunks
        if len(kept_chunks_after_budget) < len(all_documents):
            all_documents = [chunk[0] for chunk in kept_chunks_after_budget]
            all_metadatas = [chunk[1] for chunk in kept_chunks_after_budget]
            log.info(
                "full_prompt_budget_applied",
                original_chunks=budget_info["original_count"],
                kept_chunks=budget_info["kept_count"],
                dropped_chunks=budget_info["dropped_count"],
                total_prompt_tokens=budget_info["total_tokens"],
                max_tokens=budget_info["max_tokens"],
            )

        # Check if budget is exceeded even without chunks
        if not budget_info["under_budget"] and budget_info["kept_count"] == 0:
            log.error(
                "prompt_exceeds_budget_without_chunks",
                total_tokens=budget_info["total_tokens"],
                max_tokens=budget_info["max_tokens"],
                message="System prompt + question alone exceed budget",
            )
            # Return refusal - cannot answer if base prompt is too large
            return {
                "answer": get_refusal_message(sources),
                "context": "",
                "citations": [],
                "definitions": [],
                "chunks_retrieved": 0,
                "sources": sources,
                "search_mode": search_mode,
                "effective_search_mode": effective_search_mode,
                "error": "prompt_too_large",
            }
    else:
        budget_info = {"enabled": False}

    # Format final context (after budget enforcement)
    context = format_context(all_documents, all_metadatas)

    # Auto-link definitions AFTER budget enforcement (only for final context)
    # This ensures we only retrieve definitions for terms in chunks we're actually using
    definitions_dict: dict = {}
    definitions_context = ""
    if include_definitions:
        try:
            retriever = get_definitions_retriever(tuple(sources))
            # Find definitions for terms in question + final context only
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

                # Second pass: re-enforce budget WITH definitions
                # Accuracy-first: prefer keeping chunks over definitions
                if enable_budget:
                    chunks_with_metadata = list(zip(all_documents, all_metadatas))
                    source_label = ", ".join(p.upper() for p in sources)

                    # Calculate chunks before second pass for accurate drop reporting
                    chunks_before_second_pass = len(all_documents)

                    kept_chunks_final, budget_info_final = enforce_full_prompt_budget(
                        chunks=chunks_with_metadata,
                        system_prompt=SYSTEM_PROMPT,
                        question=question,
                        definitions_context=definitions_context,
                        provider_label=source_label,
                        max_tokens=MAX_CONTEXT_TOKENS,
                    )

                    # Always update budget_info to reflect actual final token count
                    budget_info = budget_info_final

                    # If definitions pushed us over budget, choose: drop definitions or chunks?
                    # Accuracy > cost: prefer chunks over definitions
                    if len(kept_chunks_final) < chunks_before_second_pass:
                        chunks_dropped = chunks_before_second_pass - len(
                            kept_chunks_final
                        )

                        log.warning(
                            "definitions_pushed_over_budget",
                            chunks_dropped=chunks_dropped,
                            total_tokens_with_definitions=budget_info_final[
                                "total_tokens"
                            ],
                        )

                        # Try dropping definitions instead of chunks (accuracy-first)
                        kept_without_definitions, budget_without_defs = (
                            enforce_full_prompt_budget(
                                chunks=chunks_with_metadata,  # Original chunks before second pass
                                system_prompt=SYSTEM_PROMPT,
                                question=question,
                                definitions_context="",  # No definitions
                                provider_label=source_label,
                                max_tokens=MAX_CONTEXT_TOKENS,
                            )
                        )

                        # If we can keep all chunks by dropping definitions, do that
                        if len(kept_without_definitions) == chunks_before_second_pass:
                            log.info(
                                "dropped_definitions_to_preserve_chunks",
                                definitions_dropped=len(definitions_dict),
                                chunks_preserved=chunks_before_second_pass,
                                total_tokens=budget_without_defs["total_tokens"],
                            )
                            # Drop definitions, keep all chunks
                            definitions_dict = {}
                            definitions_context = ""
                            budget_info = budget_without_defs
                        else:
                            # Dropping definitions wasn't enough - must drop chunks
                            all_documents = [chunk[0] for chunk in kept_chunks_final]
                            all_metadatas = [chunk[1] for chunk in kept_chunks_final]
                            context = format_context(all_documents, all_metadatas)

                            # Re-compute definitions from FINAL context only
                            # This prevents stale definitions for dropped chunks
                            original_definitions_count = len(definitions_dict)
                            try:
                                retriever = get_definitions_retriever(tuple(sources))
                                combined_text = question + " " + context
                                final_definitions_dict = (
                                    retriever.find_definitions_in_text(
                                        combined_text,
                                        max_definitions=10,
                                    )
                                )
                                if final_definitions_dict:
                                    definitions_dict = final_definitions_dict
                                    definitions_context = (
                                        format_definitions_for_context(
                                            final_definitions_dict
                                        )
                                    )
                                    log.debug(
                                        "definitions_recomputed_after_drops",
                                        original_terms=original_definitions_count,
                                        final_terms=len(definitions_dict),
                                    )

                                    # Re-enforce budget after definitions recomputation for audit accuracy
                                    _, budget_info_after_recompute = (
                                        enforce_full_prompt_budget(
                                            chunks=list(
                                                zip(all_documents, all_metadatas)
                                            ),
                                            system_prompt=SYSTEM_PROMPT,
                                            question=question,
                                            definitions_context=definitions_context,
                                            provider_label=source_label,
                                            max_tokens=MAX_CONTEXT_TOKENS,
                                        )
                                    )
                                    budget_info = budget_info_after_recompute

                                    # Try to re-add dropped chunks if definitions shrunk
                                    if (
                                        len(definitions_dict)
                                        < original_definitions_count
                                    ):
                                        tokens_freed = original_definitions_count - len(
                                            definitions_dict
                                        )
                                        if tokens_freed > 0:
                                            # Attempt to re-add chunks that were dropped
                                            chunks_to_try = chunks_with_metadata[
                                                len(all_documents) :
                                            ]
                                            if chunks_to_try:
                                                expanded_chunks = (
                                                    list(
                                                        zip(
                                                            all_documents, all_metadatas
                                                        )
                                                    )
                                                    + chunks_to_try
                                                )
                                                kept_expanded, budget_expanded = (
                                                    enforce_full_prompt_budget(
                                                        chunks=expanded_chunks,
                                                        system_prompt=SYSTEM_PROMPT,
                                                        question=question,
                                                        definitions_context=definitions_context,
                                                        provider_label=source_label,
                                                        max_tokens=MAX_CONTEXT_TOKENS,
                                                    )
                                                )
                                                chunks_readded = len(
                                                    kept_expanded
                                                ) - len(all_documents)
                                                if chunks_readded > 0:
                                                    all_documents = [
                                                        chunk[0]
                                                        for chunk in kept_expanded
                                                    ]
                                                    all_metadatas = [
                                                        chunk[1]
                                                        for chunk in kept_expanded
                                                    ]
                                                    context = format_context(
                                                        all_documents, all_metadatas
                                                    )
                                                    budget_info = budget_expanded
                                                    log.info(
                                                        "chunks_readded_after_definitions_shrink",
                                                        chunks_readded=chunks_readded,
                                                        definitions_shrink=tokens_freed,
                                                        total_tokens=budget_expanded[
                                                            "total_tokens"
                                                        ],
                                                    )
                                else:
                                    # No definitions in final context
                                    definitions_dict = {}
                                    definitions_context = ""
                                    # Update budget_info to reflect no definitions
                                    _, budget_info_no_defs = enforce_full_prompt_budget(
                                        chunks=list(zip(all_documents, all_metadatas)),
                                        system_prompt=SYSTEM_PROMPT,
                                        question=question,
                                        definitions_context="",
                                        provider_label=source_label,
                                        max_tokens=MAX_CONTEXT_TOKENS,
                                    )
                                    budget_info = budget_info_no_defs
                            except Exception as e:
                                log.warning(
                                    "definitions_recompute_failed", error=str(e)
                                )
                                definitions_dict = {}
                                definitions_context = ""

                            # Update budget_info to reflect actual final tokens after recomputing definitions
                            # This ensures debug/audit accuracy
                            _, budget_info_after_recompute = enforce_full_prompt_budget(
                                chunks=[
                                    (doc, meta)
                                    for doc, meta in zip(all_documents, all_metadatas)
                                ],
                                system_prompt=SYSTEM_PROMPT,
                                question=question,
                                definitions_context=definitions_context,
                                provider_label=source_label,
                                max_tokens=MAX_CONTEXT_TOKENS,
                            )
                            budget_info = budget_info_after_recompute

                            # Accuracy-first: attempt to restore dropped chunks if definitions shrunk
                            # Recomputed definitions are likely smaller, so we may have budget headroom
                            if chunks_dropped > 0:
                                chunks_to_try_restore = chunks_with_metadata[
                                    len(all_documents) : chunks_before_second_pass
                                ]

                                for chunk_text, chunk_meta in chunks_to_try_restore:
                                    # Try adding this chunk back
                                    test_chunks = [
                                        (doc, meta)
                                        for doc, meta in zip(
                                            all_documents, all_metadatas
                                        )
                                    ]
                                    test_chunks.append((chunk_text, chunk_meta))

                                    kept_test, budget_test = enforce_full_prompt_budget(
                                        chunks=test_chunks,
                                        system_prompt=SYSTEM_PROMPT,
                                        question=question,
                                        definitions_context=definitions_context,
                                        provider_label=source_label,
                                        max_tokens=MAX_CONTEXT_TOKENS,
                                    )

                                    # If all chunks fit (including this restored one), keep it
                                    if len(kept_test) == len(test_chunks):
                                        all_documents.append(chunk_text)
                                        all_metadatas.append(chunk_meta)
                                        budget_info = budget_test
                                        chunks_dropped -= 1
                                        log.debug(
                                            "chunk_restored_after_definitions_shrink",
                                            chunk_relevance=chunk_meta.get(
                                                "_relevance_score", 0.0
                                            ),
                                            total_tokens=budget_test["total_tokens"],
                                        )
                                    else:
                                        # Can't fit this chunk, stop trying
                                        break

                                # Update context with any restored chunks
                                if chunks_dropped < chunks_before_second_pass - len(
                                    kept_chunks_final
                                ):
                                    context = format_context(
                                        all_documents, all_metadatas
                                    )
                                    log.info(
                                        "chunks_restored_after_definitions_shrink",
                                        chunks_restored=(
                                            chunks_before_second_pass
                                            - len(kept_chunks_final)
                                            - chunks_dropped
                                        ),
                                        final_chunk_count=len(all_documents),
                                        total_tokens=budget_info["total_tokens"],
                                    )

                            log.info(
                                "dropped_chunks_despite_definitions",
                                chunks_dropped=chunks_dropped,
                                definitions_kept=len(definitions_dict),
                                total_tokens=budget_info["total_tokens"],
                            )
        except Exception as e:
            log.warning("definitions_retrieval_failed", error=str(e))

    # Post-budget check: Refuse if no context remains after budget enforcement
    # This prevents answering with empty context (budget can drop all chunks)
    if len(all_documents) == 0:
        log.error(
            "empty_context_after_budget",
            budget_enabled=enable_budget,
            original_chunks=budget_info.get("original_count", 0),
        )

        refusal_message = get_refusal_message(sources)
        reason_detail = get_refusal_reason_message("empty_context_after_budget")

        response = {
            "answer": refusal_message,
            "context": "",
            "citations": [],
            "definitions": [],
            "chunks_retrieved": budget_info.get("original_count", 0),
            "sources": sources,
            "search_mode": search_mode,
            "effective_search_mode": effective_search_mode,
            "refused": True,
            "refusal_reason": "empty_context_after_budget",
            "refusal_detail": reason_detail,
        }

        if debug:
            from app.budget import count_tokens

            # Build comprehensive debug for refusal case
            # Use format_retrieval_info for rich debug output with scores/ranks
            retrieval_info = format_retrieval_info(all_search_results, sources)

            debug_dict = build_debug_output(
                original_query=question,
                normalized_query=normalized_question,
                normalization_applied=(
                    question.lower().strip() != normalized_question.lower().strip()
                ),
                normalization_failed=normalization_failed,
                sources=sources,
                search_mode=search_mode,
                effective_search_mode=effective_search_mode,
                retrieval_info=retrieval_info,
                reranking_info=rerank_info if rerank_info else None,
                budget_info=budget_info if budget_info else None,
                confidence_gate_info=gate_info if gate_info else None,
                final_chunks_count=0,
                final_context_tokens=0,
                definitions_count=0,
                llm_called=False,
                validation_info={
                    "refusal": True,
                    "reason": "empty_context_after_budget",
                },
            )
            response["debug"] = debug_dict

            # Always write debug output (stderr always, file if DEBUG_LOG_ENABLED=True)
            write_debug_output(debug_dict, write_to_stderr=True)

        # Audit logging (always-on for compliance)
        from app.audit import calculate_latency_ms
        from app.audit import log_query_response

        log_query_response(
            query=question,
            answer=str(response["answer"]),
            sources=sources,
            chunks_retrieved=budget_info.get("original_count", 0),
            chunks_used=0,
            tokens_input=0,
            tokens_output=0,
            latency_ms=calculate_latency_ms(start_time),
            refused=True,
            refusal_reason="empty_context_after_budget",
            write_to_console=log_to_console,
        )

        return response

    # Build final prompt (source label already set during budget enforcement)
    source_label = ", ".join(p.upper() for p in sources)

    # Use appropriate prompt based on whether definitions were found
    if definitions_context:
        prompt = QA_PROMPT.format(
            context=context,
            definitions_section=definitions_context,
            question=question,
            source=source_label,
        )
    else:
        prompt = QA_PROMPT_NO_DEFINITIONS.format(
            context=context,
            question=question,
            source=source_label,
        )

    # Call LLM
    log.debug("calling_llm")
    try:
        llm = get_llm()
        # Format system prompt with source label to avoid literal {source} placeholder
        formatted_system_prompt = SYSTEM_PROMPT.format(source=source_label)
        answer = llm.generate(system=formatted_system_prompt, prompt=prompt)

        # Validate LLM output
        validation = validate_llm_output(answer, sources)

        if not validation.is_valid:
            log.warning(
                "llm_output_validation_failed_retrying",
                errors=validation.errors,
                is_refusal=validation.is_refusal,
            )

            # Retry once with stricter system prompt
            stricter_prompt = get_stricter_system_prompt(
                formatted_system_prompt, sources
            )
            answer = llm.generate(system=stricter_prompt, prompt=prompt)

            # Validate retry
            validation_retry = validate_llm_output(answer, sources)

            if not validation_retry.is_valid:
                # If retry also fails, return canonical refusal
                log.error(
                    "llm_output_validation_failed_after_retry",
                    errors=validation_retry.errors,
                    is_refusal=validation_retry.is_refusal,
                )
                answer = f"""## Answer
{get_refusal_message(sources)}

The system could not generate a properly formatted response. Please try rephrasing your question or contact support if this persists."""
            else:
                log.info("llm_output_validation_succeeded_on_retry")
        else:
            if validation.warnings:
                log.info(
                    "llm_output_has_warnings",
                    warnings=validation.warnings,
                )

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
        source = meta.get("source", "unknown")
        # Use document_path in key to prevent same-filename-different-subdirectory collisions
        key = (source, doc_path, section, page_start, page_end)
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "document": doc_path,
                    "section": section,
                    "page_start": page_start,
                    "page_end": page_end,
                    "source": meta.get("source", "unknown"),
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
        "sources": sources,
        "search_mode": search_mode,
        "effective_search_mode": effective_search_mode,
    }

    # Add debug information if requested
    if debug:
        from app.budget import count_tokens

        # Count final context tokens
        final_context_tokens = count_tokens(context) if context else 0

        # Format retrieval info with scores and ranks
        retrieval_info = format_retrieval_info(all_search_results, sources)

        # Build comprehensive debug output using Phase 8 module
        debug_dict = build_debug_output(
            original_query=question,
            normalized_query=normalized_question,
            normalization_applied=(
                question.lower().strip() != normalized_question.lower().strip()
            ),
            normalization_failed=normalization_failed,
            sources=sources,
            search_mode=search_mode,
            effective_search_mode=effective_search_mode,
            retrieval_info=retrieval_info,
            reranking_info=rerank_info if rerank_info else None,
            budget_info=budget_info if budget_info else None,
            confidence_gate_info=gate_info if gate_info else None,
            final_chunks_count=len(all_documents),
            final_context_tokens=final_context_tokens,
            definitions_count=len(definitions_output),
            llm_called=True,  # We always call LLM if we reach this point
            validation_info={
                "validation_enabled": True,
                "answer_length": len(answer),
            }
            if answer
            else None,
        )
        response["debug"] = debug_dict

        # Always write debug output when debug=True (stderr always, file if enabled)
        write_debug_output(debug_dict, write_to_stderr=True)

    # Audit logging (always-on for compliance)
    from app.audit import calculate_latency_ms
    from app.audit import log_query_response
    from app.budget import count_tokens

    # Count tokens for audit (prompt + completion)
    tokens_input = count_tokens(prompt) if "prompt" in locals() else 0
    tokens_output = count_tokens(answer) if answer else 0

    log_query_response(
        query=question,
        answer=answer,
        sources=sources,
        chunks_retrieved=len(all_search_results)
        if "all_search_results" in locals()
        else 0,
        chunks_used=len(all_documents),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        latency_ms=calculate_latency_ms(start_time),
        refused=False,
        refusal_reason=None,
        write_to_console=log_to_console,
    )

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
