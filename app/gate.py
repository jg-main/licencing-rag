# app/gate.py
"""Confidence gating for query responses.

This module implements code-enforced refusal logic to prevent answering
when retrieval confidence is too low. This is a critical accuracy safeguard
that cannot be bypassed by prompt engineering.

Gating happens BEFORE the LLM call to save costs and prevent hallucinations.

Two-Tier Gating Strategy:
1. Reranked scores (0-3 scale): Use threshold-based gating (RELEVANCE_THRESHOLD=2)
2. Retrieval scores (vector/BM25/RRF): Use absolute minimum + top-1/top-2 ratio gating

This prevents false refusals/accepts when reranking is disabled or fallback is used.
"""

from typing import Any

from app.logging import get_logger

log = get_logger(__name__)

# Thresholds for confidence gating
RELEVANCE_THRESHOLD = 2  # Minimum relevance score (2 = RELEVANT)
MIN_CHUNKS_REQUIRED = 1  # Minimum number of chunks above threshold

# Retrieval-score gating thresholds (when reranking disabled/fallback)
RETRIEVAL_MIN_SCORE = 0.05  # Top score must exceed minimum (prevents weak positives)
RETRIEVAL_MIN_RATIO = 1.2  # Top-1 must be >= 1.2 × top-2 (clear winner)


def should_refuse(
    chunks: list[Any],
    scores_are_reranked: bool = True,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
    min_chunks: int = MIN_CHUNKS_REQUIRED,
    retrieval_min_score: float = RETRIEVAL_MIN_SCORE,
    retrieval_min_ratio: float = RETRIEVAL_MIN_RATIO,
) -> tuple[bool, str | None]:
    """Determine if query should be refused based on retrieval confidence.

    Two-tier gating strategy:
    - If scores_are_reranked=True: Use 0-3 threshold-based gating
    - If scores_are_reranked=False: Use absolute minimum + top-1/top-2 ratio gating

    Reranked scores (0-3) refusal rules:
    1. Refuse if no chunks retrieved
    2. Refuse if no chunk score >= relevance_threshold
    3. Refuse if top chunk score < relevance_threshold
    4. Refuse if fewer than min_chunks above threshold

    Retrieval scores refusal rules:
    1. Refuse if no chunks retrieved
    2. Refuse if top score <= absolute minimum (prevents negative/weak positives)
    3. Refuse if top-1/top-2 ratio < min ratio (no clear winner)

    Args:
        chunks: List of chunk objects with relevance_score attribute.
        scores_are_reranked: True if scores are 0-3 reranked scores, False if raw retrieval.
        relevance_threshold: Minimum score for reranked chunks (default: 2).
        min_chunks: Minimum chunks above threshold for reranked (default: 1).
        retrieval_min_score: Absolute minimum for retrieval scores (default: 0.05).
        retrieval_min_ratio: Minimum top-1/top-2 ratio for retrieval (default: 1.2).

    Returns:
        Tuple of (should_refuse: bool, reason: str | None)
        - If should_refuse is True, reason contains the refusal explanation
        - If should_refuse is False, reason is None
    """
    # Rule 1: No chunks retrieved (applies to both tiers)
    if not chunks:
        reason = "no_chunks_retrieved"
        log.warning("confidence_gate_refuse", reason=reason, gate_type="both")
        return True, reason

    # Extract relevance scores
    scores = []
    for chunk in chunks:
        # Handle both dict-like and object-like access
        if hasattr(chunk, "relevance_score"):
            scores.append(chunk.relevance_score)
        elif isinstance(chunk, dict) and "relevance_score" in chunk:
            scores.append(chunk["relevance_score"])
        elif hasattr(chunk, "metadata") and isinstance(chunk.metadata, dict):
            scores.append(chunk.metadata.get("_relevance_score", 0))
        else:
            # Fallback: assume score of 0 if not found
            scores.append(0)

    if not scores:
        reason = "no_relevance_scores_found"
        log.warning("confidence_gate_refuse", reason=reason, gate_type="both")
        return True, reason

    # Apply appropriate gating strategy based on score type
    if scores_are_reranked:
        # Tier 1: Reranked scores (0-3 scale)
        return _gate_reranked_scores(scores, relevance_threshold, min_chunks)
    else:
        # Tier 2: Retrieval scores (absolute minimum + top-1/top-2 ratio)
        return _gate_retrieval_scores(scores, retrieval_min_score, retrieval_min_ratio)


def _gate_reranked_scores(
    scores: list[float],
    relevance_threshold: float,
    min_chunks: int,
) -> tuple[bool, str | None]:
    """Gate using 0-3 reranked scores with threshold-based logic."""
    chunks_above_threshold = [s for s in scores if s >= relevance_threshold]

    # Rule 2: No chunks above threshold
    if not chunks_above_threshold:
        reason = "all_chunks_below_threshold"
        log.warning(
            "confidence_gate_refuse",
            reason=reason,
            gate_type="reranked",
            top_score=max(scores),
            threshold=relevance_threshold,
        )
        return True, reason

    # Rule 3: Not enough chunks above threshold
    if len(chunks_above_threshold) < min_chunks:
        reason = "insufficient_chunks_above_threshold"
        log.warning(
            "confidence_gate_refuse",
            reason=reason,
            gate_type="reranked",
            chunks_above=len(chunks_above_threshold),
            min_required=min_chunks,
            threshold=relevance_threshold,
        )
        return True, reason

    # Rule 4: Top score below threshold
    top_score = max(scores)
    if top_score < relevance_threshold:
        reason = "top_score_below_threshold"
        log.warning(
            "confidence_gate_refuse",
            reason=reason,
            gate_type="reranked",
            top_score=top_score,
            threshold=relevance_threshold,
        )
        return True, reason

    # Passed all checks - proceed with answer
    log.info(
        "confidence_gate_passed",
        gate_type="reranked",
        top_score=top_score,
        chunks_above_threshold=len(chunks_above_threshold),
        threshold=relevance_threshold,
    )
    return False, None


def _gate_retrieval_scores(
    scores: list[float],
    min_score: float,
    min_ratio: float,
) -> tuple[bool, str | None]:
    """Gate using raw retrieval scores with absolute threshold + top-1/top-2 ratio.

    This prevents false refusals when reranking is disabled or fallback is used,
    since retrieval scores are on a different scale than 0-3 reranked scores.

    Top-1/top-2 ratio is more robust than median-gap for small score lists and
    works consistently across different retrieval sources (vector/BM25/RRF).
    """
    if len(scores) < 2:
        # With only 1 chunk, can't compute ratio - just check if score > min_score
        if scores[0] <= min_score:
            reason = "retrieval_score_too_low"
            log.warning(
                "confidence_gate_refuse",
                reason=reason,
                gate_type="retrieval",
                score=scores[0],
                min_score=min_score,
            )
            return True, reason
        log.info(
            "confidence_gate_passed",
            gate_type="retrieval",
            score=scores[0],
            note="single_chunk",
        )
        return False, None

    # Get top-2 scores
    sorted_scores = sorted(scores, reverse=True)
    top1 = sorted_scores[0]
    top2 = sorted_scores[1]

    # Rule 2: Top score below absolute minimum (prevents negative/weak positives)
    if top1 <= min_score:
        reason = "retrieval_top_below_minimum"
        log.warning(
            "confidence_gate_refuse",
            reason=reason,
            gate_type="retrieval",
            top_score=top1,
            min_score=min_score,
        )
        return True, reason

    # Rule 3: Top-1/top-2 ratio too small (no clear winner)
    # If top2 is 0 or negative, use absolute difference instead
    if top2 > 0:
        ratio = top1 / top2
    else:
        # If top2 <= 0, require top1 to be at least 2x min_score
        # This prevents accepting weak evidence (e.g., top1=0.06, top2=-0.01)
        if top1 < 2 * min_score:
            reason = "retrieval_top1_too_weak_with_negative_top2"
            log.warning(
                "confidence_gate_refuse",
                reason=reason,
                gate_type="retrieval",
                top1=top1,
                top2=top2,
                min_score=min_score,
                required_min=2 * min_score,
            )
            return True, reason
        # Use absolute difference as a proxy for ratio
        ratio = (top1 - top2) / min_score if min_score > 0 else float("inf")

    if ratio < min_ratio:
        reason = "retrieval_insufficient_ratio"
        log.warning(
            "confidence_gate_refuse",
            reason=reason,
            gate_type="retrieval",
            top1=top1,
            top2=top2,
            ratio=ratio,
            min_ratio=min_ratio,
        )
        return True, reason

    # Passed all checks - proceed with answer
    log.info(
        "confidence_gate_passed",
        gate_type="retrieval",
        top1=top1,
        top2=top2,
        ratio=ratio,
        min_score=min_score,
    )
    return False, None


def get_refusal_reason_message(reason: str | None) -> str:
    """Get human-readable refusal message for a given reason.

    Args:
        reason: Refusal reason code from should_refuse().

    Returns:
        Human-readable explanation of why the query was refused.
    """
    messages = {
        # Reranked score reasons
        "no_chunks_retrieved": "No relevant information found in the documents.",
        "no_relevance_scores_found": "Unable to assess relevance of retrieved information.",
        "all_chunks_below_threshold": "No sufficiently relevant information found.",
        "insufficient_chunks_above_threshold": "Insufficient relevant information to provide a reliable answer.",
        "top_score_below_threshold": "The most relevant information found does not meet confidence threshold.",
        # Retrieval score reasons
        "retrieval_score_too_low": "Retrieved information has insufficient relevance score.",
        "retrieval_top_below_minimum": (
            "The system found some information, but the confidence scores are too low. "
            "This suggests the available data may not be sufficiently relevant to answer "
            "your question with confidence."
        ),
        "retrieval_insufficient_ratio": "No clear best match found - top results have similar confidence scores.",
        "retrieval_top1_too_weak_with_negative_top2": (
            "The system found some information, but the top result is too weak "
            "and other results have negative confidence scores. "
            "This suggests insufficient relevant information to answer your question."
        ),
        # Post-budget reason
        "empty_context_after_budget": "Token budget constraints eliminated all retrieved information.",
    }

    return messages.get(
        reason or "",
        "Unable to provide a reliable answer based on available information.",
    )
