# app/budget.py
"""Context budget enforcement for token-limited LLM input.

This module ensures the combined context sent to the LLM stays within
budget limits to control costs and reduce hallucination risk. Uses tiktoken
for accurate token counting with GPT-4.1.

Budget enforcement uses an accuracy-first approach: it builds the FULL prompt
(system + QA template + question + definitions + context), measures total tokens,
and iteratively drops lowest-priority chunks until within the 60k limit.
"""

from typing import Any

import tiktoken

from app.logging import get_logger

log = get_logger(__name__)


def get_encoding() -> tiktoken.Encoding:
    """Get tiktoken encoding for the LLM model.

    Returns:
        Encoding for GPT-4.1.
    """
    # GPT-4.1 uses cl100k_base encoding
    # Note: tiktoken doesn't recognize 'gpt-4.1' yet, but it uses the same
    # cl100k_base encoding as gpt-4, so we use gpt-4 as the model identifier
    return tiktoken.encoding_for_model("gpt-4")


def count_tokens(text: str, encoding: tiktoken.Encoding | None = None) -> int:
    """Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for.
        encoding: Optional encoding to use. If None, gets encoding for LLM_MODEL.

    Returns:
        Number of tokens.
    """
    if encoding is None:
        encoding = get_encoding()
    return len(encoding.encode(text))


def format_chunk_for_context(text: str, metadata: dict[str, Any]) -> str:
    """Format a single chunk as it will appear in the LLM context.

    This EXACTLY matches the format used in query.py's format_context() function
    to ensure accurate token counting for budget enforcement.

    Args:
        text: Chunk text.
        metadata: Chunk metadata.

    Returns:
        Formatted string as it will appear in context.
    """
    provider = metadata.get("provider", "unknown").upper()
    # Prefer document_path (includes subdirectory) for unambiguous citations
    source = metadata.get("document_path") or metadata.get("document_name", "Unknown")
    section = metadata.get("section_heading", "N/A")
    page_start = metadata.get("page_start", "?")
    page_end = metadata.get("page_end", "?")

    if page_start == page_end:
        page_info = f"Page {page_start}"
    else:
        page_info = f"Pages {page_start}-{page_end}"

    header = f"--- [{provider}] {source} | {section} | {page_info} ---"
    return f"{header}\n{text}"


def measure_full_prompt_tokens(
    system_prompt: str,
    qa_prompt: str,
    encoding: tiktoken.Encoding | None = None,
) -> int:
    """Measure tokens in complete prompt including all components.

    Args:
        system_prompt: System prompt text.
        qa_prompt: QA prompt with context, question, definitions.
        encoding: Optional tiktoken encoding.

    Returns:
        Total token count for complete prompt.
    """
    if encoding is None:
        encoding = get_encoding()

    # System prompt is sent separately, so count both
    system_tokens = count_tokens(system_prompt, encoding)
    prompt_tokens = count_tokens(qa_prompt, encoding)

    return system_tokens + prompt_tokens


def enforce_full_prompt_budget(
    chunks: list[tuple[str, dict[str, Any]]],
    system_prompt: str,
    question: str,
    definitions_context: str,
    provider_label: str,
    max_tokens: int,
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    """Enforce token budget on FULL prompt by measuring complete output.

    This is the accuracy-first approach: build the actual prompt, measure it,
    and iteratively drop lowest-priority chunks until within budget.

    Args:
        chunks: List of (text, metadata) tuples.
        system_prompt: System prompt text.
        question: User question.
        definitions_context: Formatted definitions section (or empty string).
        provider_label: Provider label (e.g., "CME").
        max_tokens: Maximum tokens for complete prompt.

    Returns:
        Tuple of (kept_chunks, budget_info) where budget_info contains:
        - enabled: Always True for this function
        - original_count: Number of chunks before enforcement
        - kept_count: Number of chunks after enforcement
        - dropped_count: Number of chunks dropped
        - total_tokens: Total tokens in full prompt
        - max_tokens: Budget limit
        - under_budget: Whether we stayed under budget
        - dropped_chunks: List of dropped chunk info (if any)
    """
    if not chunks:
        # Build prompt with no context to get baseline
        from app.query import format_context

        context = format_context([], [])
        if definitions_context:
            from app.prompts import QA_PROMPT

            qa_prompt = QA_PROMPT.format(
                context=context,
                definitions_section=definitions_context,
                question=question,
                provider=provider_label,
            )
        else:
            from app.prompts import QA_PROMPT_NO_DEFINITIONS

            qa_prompt = QA_PROMPT_NO_DEFINITIONS.format(
                context=context,
                question=question,
                provider=provider_label,
            )

        encoding = get_encoding()
        total_tokens = measure_full_prompt_tokens(system_prompt, qa_prompt, encoding)

        return [], {
            "enabled": True,
            "original_count": 0,
            "kept_count": 0,
            "dropped_count": 0,
            "total_tokens": total_tokens,
            "max_tokens": max_tokens,
            "under_budget": total_tokens <= max_tokens,
            "dropped_chunks": [],
        }

    encoding = get_encoding()

    # Score each chunk for priority sorting
    scored_chunks: list[tuple[str, dict[str, Any], float, int]] = []
    for text, metadata in chunks:
        # Extract relevance score from metadata (from reranking) or default to 0
        relevance_score = metadata.get("_relevance_score", 0.0)
        # Estimate token count for sorting (not used for final budget)
        formatted = format_chunk_for_context(text, metadata)
        token_count = count_tokens(formatted, encoding)
        scored_chunks.append((text, metadata, relevance_score, token_count))

    # Sort by priority: relevance (desc) > length (asc)
    sorted_chunks = sorted(
        scored_chunks,
        key=lambda x: (-x[2], x[3]),  # -score, +tokens
    )

    # Import format_context from query module to build actual context
    from app.prompts import QA_PROMPT
    from app.prompts import QA_PROMPT_NO_DEFINITIONS
    from app.query import format_context

    # Start with all chunks and iteratively drop lowest-priority until within budget
    current_chunks = [(text, meta) for text, meta, _, _ in sorted_chunks]
    dropped_chunks: list[dict[str, Any]] = []

    while current_chunks:
        # Build actual context
        docs = [text for text, _ in current_chunks]
        metas = [meta for _, meta in current_chunks]
        context = format_context(docs, metas)

        # Build actual prompt
        if definitions_context:
            qa_prompt = QA_PROMPT.format(
                context=context,
                definitions_section=definitions_context,
                question=question,
                provider=provider_label,
            )
        else:
            qa_prompt = QA_PROMPT_NO_DEFINITIONS.format(
                context=context,
                question=question,
                provider=provider_label,
            )

        # Measure FULL prompt tokens
        total_tokens = measure_full_prompt_tokens(system_prompt, qa_prompt, encoding)

        if total_tokens <= max_tokens:
            # Within budget - we're done
            budget_info = {
                "enabled": True,
                "original_count": len(chunks),
                "kept_count": len(current_chunks),
                "dropped_count": len(dropped_chunks),
                "total_tokens": total_tokens,
                "max_tokens": max_tokens,
                "under_budget": True,
                "dropped_chunks": dropped_chunks,
            }

            if dropped_chunks:
                log.warning(
                    "full_prompt_budget_enforcement",
                    original=len(chunks),
                    kept=len(current_chunks),
                    dropped=len(dropped_chunks),
                    total_tokens=total_tokens,
                    max_tokens=max_tokens,
                )
            else:
                log.info(
                    "full_prompt_within_budget",
                    chunk_count=len(current_chunks),
                    total_tokens=total_tokens,
                    max_tokens=max_tokens,
                )

            return current_chunks, budget_info

        # Over budget - drop lowest-priority chunk (last in list)
        dropped_text, dropped_meta = current_chunks.pop()
        # Find the score and token count for this chunk
        for text, meta, score, tokens in sorted_chunks:
            if text == dropped_text and meta == dropped_meta:
                dropped_chunks.append(
                    {
                        "chunk_id": dropped_meta.get("chunk_id", "unknown"),
                        "relevance_score": score,
                        "token_count": tokens,
                        "reason": "full_prompt_exceeded_budget",
                    }
                )
                break

    # All chunks dropped - prompt is still too large (edge case)
    # This means system + QA template + question + definitions alone exceed budget
    context = format_context([], [])
    if definitions_context:
        qa_prompt = QA_PROMPT.format(
            context=context,
            definitions_section=definitions_context,
            question=question,
            provider=provider_label,
        )
    else:
        qa_prompt = QA_PROMPT_NO_DEFINITIONS.format(
            context=context,
            question=question,
            provider=provider_label,
        )

    total_tokens = measure_full_prompt_tokens(system_prompt, qa_prompt, encoding)

    log.error(
        "full_prompt_budget_exceeded_with_no_chunks",
        total_tokens=total_tokens,
        max_tokens=max_tokens,
        message="System+QA template+question+definitions alone exceed budget",
    )

    return [], {
        "enabled": True,
        "original_count": len(chunks),
        "kept_count": 0,
        "dropped_count": len(chunks),
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "under_budget": False,
        "dropped_chunks": dropped_chunks,
    }


def enforce_context_budget(
    chunks: list[tuple[str, dict[str, Any]]],
    max_tokens: int = 50000,  # Conservative default (old chunk-only approach)
) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, Any]]:
    """Enforce token budget on context chunks.

    Counts tokens for all chunks and drops lowest-priority chunks if over budget.
    Prioritizes chunks by:
    1. Relevance score (from metadata, if available from reranking)
    2. Shorter length when scores are tied

    Args:
        chunks: List of (text, metadata) tuples.
        max_tokens: Maximum tokens allowed for all chunks combined.

    Returns:
        Tuple of (kept_chunks, budget_info) where budget_info contains:
        - original_count: Number of chunks before enforcement
        - kept_count: Number of chunks after enforcement
        - dropped_count: Number of chunks dropped
        - total_tokens: Total tokens in kept chunks
        - under_budget: Whether we stayed under budget
        - dropped_chunks: List of dropped chunk info (if any)
    """
    if not chunks:
        return [], {
            "original_count": 0,
            "kept_count": 0,
            "dropped_count": 0,
            "total_tokens": 0,
            "under_budget": True,
            "dropped_chunks": [],
        }

    encoding = get_encoding()

    # Score and measure each chunk
    scored_chunks: list[tuple[str, dict[str, Any], int, int]] = []
    for text, metadata in chunks:
        formatted_text = format_chunk_for_context(text, metadata)
        token_count = count_tokens(formatted_text, encoding)
        # Extract relevance score from metadata (from reranking) or default to 0
        relevance_score = metadata.get("_relevance_score", 0)
        scored_chunks.append((text, metadata, relevance_score, token_count))

    # Sort by priority:
    # 1. Relevance score (descending) - keep most relevant
    # 2. Token count (ascending) - prefer shorter when scores tied
    sorted_chunks = sorted(
        scored_chunks,
        key=lambda x: (-x[2], x[3]),  # -score, +tokens
    )

    # Accumulate chunks until budget exceeded
    kept_chunks: list[tuple[str, dict[str, Any]]] = []
    dropped_chunks: list[dict[str, Any]] = []
    total_tokens = 0

    for text, metadata, score, token_count in sorted_chunks:
        if total_tokens + token_count <= max_tokens:
            kept_chunks.append((text, metadata))
            total_tokens += token_count
        else:
            # Drop this chunk - over budget
            dropped_chunks.append(
                {
                    "chunk_id": metadata.get("chunk_id", "unknown"),
                    "relevance_score": score,
                    "token_count": token_count,
                    "reason": "exceeded_token_budget",
                }
            )

    budget_info = {
        "original_count": len(chunks),
        "kept_count": len(kept_chunks),
        "dropped_count": len(dropped_chunks),
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "under_budget": total_tokens <= max_tokens,
        "dropped_chunks": dropped_chunks,
    }

    if dropped_chunks:
        log.warning(
            "budget_enforcement_dropped_chunks",
            original=len(chunks),
            kept=len(kept_chunks),
            dropped=len(dropped_chunks),
            total_tokens=total_tokens,
            max_tokens=max_tokens,
        )
    else:
        log.info(
            "budget_enforcement_passed",
            chunk_count=len(chunks),
            total_tokens=total_tokens,
            max_tokens=max_tokens,
        )

    return kept_chunks, budget_info
