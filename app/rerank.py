# app/rerank.py
"""LLM-based chunk reranking for improved retrieval quality.

This module implements LLM reranking to score retrieved chunks based on
relevance to the user's question. Uses GPT-4.1 to assign 0-3 relevance scores,
then selects the top-scoring chunks for context.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.config import LLM_MODEL
from app.config import MAX_CHUNK_LENGTH_FOR_RERANKING
from app.config import MAX_CHUNKS_AFTER_RERANKING
from app.config import MIN_RERANKING_SCORE
from app.config import RERANKING_INCLUDE_EXPLANATIONS
from app.config import RERANKING_TIMEOUT
from app.llm import generate
from app.logging import get_logger

log = get_logger(__name__)


@dataclass
class ScoredChunk:
    """A chunk with its relevance score from LLM reranking."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    original_score: float
    relevance_score: int  # 0-3 scale from LLM
    explanation: str  # Why this score was assigned
    source: str  # "vector", "keyword", or "hybrid"


# Scoring prompt for LLM reranking
RERANKING_SYSTEM_PROMPT = """You are a relevance scoring expert for a license agreement question-answering system.

Your task is to score how relevant a document chunk is to answering a specific question.

Use this 4-point scale:
- Score 3: HIGHLY RELEVANT - Chunk directly answers the question or contains critical information needed to answer it
- Score 2: RELEVANT - Chunk contains useful context or related information that helps answer the question
- Score 1: SOMEWHAT RELEVANT - Chunk mentions related topics but doesn't directly help answer the question
- Score 0: NOT RELEVANT - Chunk is about different topics entirely

IMPORTANT:
- Focus on whether the chunk helps ANSWER the question, not just whether it contains the exact keywords
- A chunk can be highly relevant even if it uses different terminology than the question
- Consider the semantic meaning and context, not just literal keyword matches
- Score 3 if the chunk provides specific requirements, procedures, or details that directly address what is being asked

Score 0 only for chunks that are truly off-topic, not for chunks that answer the question using different words."""

# Minimal prompt for cost efficiency (default)
RERANKING_PROMPT_MINIMAL = """Question: {question}

Chunk to score:
{chunk_text}

Respond with ONLY a single digit (0-3) indicating the relevance score. No other text."""

# Detailed prompt with explanations (for debugging)
RERANKING_PROMPT_DETAILED = """Question: {question}

Chunk to score:
{chunk_text}

Provide your score (0-3) and a brief explanation (one sentence).

Format your response exactly as:
Score: <number>
Explanation: <reason>"""


def truncate_chunk(text: str, max_length: int = MAX_CHUNK_LENGTH_FOR_RERANKING) -> str:
    """Truncate chunk text for efficient reranking.

    Args:
        text: Chunk text to truncate.
        max_length: Maximum character length.

    Returns:
        Truncated text with ellipsis if truncated.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def parse_score_response(
    response: str, include_explanations: bool = RERANKING_INCLUDE_EXPLANATIONS
) -> tuple[int, str]:
    """Parse LLM response to extract score and explanation.

    Supports two formats:
    1. Minimal (single digit): "2"
    2. Detailed: "Score: 2\nExplanation: Contains fee schedule information..."

    Args:
        response: Raw LLM response text.
        include_explanations: Whether explanations were requested.

    Returns:
        Tuple of (score, explanation). Defaults to (1, response) if parsing fails.
    """
    response = response.strip()

    # Try minimal format first (single digit)
    if len(response) <= 3 and response.isdigit():
        parsed = int(response)
        score = max(0, min(3, parsed))
        return score, "No explanation provided (minimal mode)"

    # Try detailed format
    lines = response.split("\n")
    score = 1  # Default to somewhat relevant
    explanation = response

    for line in lines:
        line = line.strip()
        if line.lower().startswith("score:"):
            try:
                score_str = line.split(":", 1)[1].strip()
                # Extract first digit found
                for char in score_str:
                    if char.isdigit():
                        parsed = int(char)
                        # Clamp to 0-3 range
                        score = max(0, min(3, parsed))
                        break
            except (ValueError, IndexError):
                log.warning("score_parse_failed", line=line)

        elif line.lower().startswith("explanation:"):
            explanation = line.split(":", 1)[1].strip()

    return score, explanation


def score_chunk(
    chunk_id: str,
    chunk_text: str,
    question: str,
    model: str = LLM_MODEL,
    include_explanations: bool = RERANKING_INCLUDE_EXPLANATIONS,
) -> tuple[int, str]:
    """Score a single chunk for relevance using LLM.

    Args:
        chunk_id: Chunk identifier for logging.
        chunk_text: The chunk text to score.
        question: User's question.
        model: LLM model to use for scoring.
        include_explanations: If True, request detailed explanations (costs ~50% more).

    Returns:
        Tuple of (relevance_score, explanation).
    """
    # Truncate chunk for efficiency
    truncated_text = truncate_chunk(chunk_text)

    # Choose prompt based on whether explanations are needed
    prompt_template = (
        RERANKING_PROMPT_DETAILED if include_explanations else RERANKING_PROMPT_MINIMAL
    )
    prompt = prompt_template.format(
        question=question,
        chunk_text=truncated_text,
    )

    # Adjust max_tokens based on mode
    max_tokens = 150 if include_explanations else 10

    try:
        # Call LLM with low temperature for consistent scoring
        response = generate(
            system=RERANKING_SYSTEM_PROMPT,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=0.0,
            timeout=RERANKING_TIMEOUT,  # Prevent hanging on slow API calls
        )

        score, explanation = parse_score_response(response, include_explanations)

        log.debug(
            "chunk_scored",
            chunk_id=chunk_id,
            score=score,
            explanation=explanation[:100] if include_explanations else "(minimal mode)",
        )

        return score, explanation

    except Exception as e:
        log.warning("chunk_scoring_failed", chunk_id=chunk_id, error=str(e))
        # Default to somewhat relevant on error (timeout or API failure)
        return 1, f"Scoring failed: {str(e)}"


def score_chunk_wrapper(args: tuple) -> tuple[int, int, str]:
    """Wrapper for parallel execution.

    Args:
        args: Tuple of (index, chunk_id, chunk_text, question, model).

    Returns:
        Tuple of (index, relevance_score, explanation).
    """
    index, chunk_id, chunk_text, question, model = args
    score, explanation = score_chunk(chunk_id, chunk_text, question, model)
    return index, score, explanation


def rerank_chunks(
    chunks: list[dict[str, Any]],
    question: str,
    min_score: int = MIN_RERANKING_SCORE,
    max_chunks: int = MAX_CHUNKS_AFTER_RERANKING,
    model: str = LLM_MODEL,
    use_parallel: bool = True,
) -> tuple[list[ScoredChunk], list[ScoredChunk]]:
    """Rerank retrieved chunks using LLM scoring.

    Args:
        chunks: List of chunk dictionaries with keys: chunk_id, text, metadata,
                score (original retrieval score), source (retrieval method).
        question: User's question for relevance scoring.
        top_k: Number of top-scored chunks to keep (3-5 recommended).
        model: LLM model to use for scoring.
        use_parallel: Whether to score chunks in parallel (faster but more API calls).

    Returns:
        Tuple of (kept_chunks, dropped_chunks) where each is a list of ScoredChunk.
        kept_chunks are sorted by relevance_score descending.
    """
    if not chunks:
        log.debug("rerank_no_chunks")
        return [], []

    log.info(
        "rerank_started",
        chunk_count=len(chunks),
        min_score=min_score,
        max_chunks=max_chunks,
        parallel=use_parallel,
    )

    scored_chunks: list[ScoredChunk] = []

    if use_parallel:
        # Parallel execution for speed
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Prepare arguments
            score_args = [
                (
                    i,
                    chunk["chunk_id"],
                    chunk["text"],
                    question,
                    model,
                )
                for i, chunk in enumerate(chunks)
            ]

            # Execute in parallel
            results = list(executor.map(score_chunk_wrapper, score_args))

            # Build scored chunks from results
            for index, relevance_score, explanation in results:
                chunk = chunks[index]
                scored_chunks.append(
                    ScoredChunk(
                        chunk_id=chunk["chunk_id"],
                        text=chunk["text"],
                        metadata=chunk["metadata"],
                        original_score=chunk.get("score", 0.0),
                        relevance_score=relevance_score,
                        explanation=explanation,
                        source=chunk.get("source", "unknown"),
                    )
                )
    else:
        # Sequential execution
        for chunk in chunks:
            relevance_score, explanation = score_chunk(
                chunk_id=chunk["chunk_id"],
                chunk_text=chunk["text"],
                question=question,
                model=model,
            )
            scored_chunks.append(
                ScoredChunk(
                    chunk_id=chunk["chunk_id"],
                    text=chunk["text"],
                    metadata=chunk["metadata"],
                    original_score=chunk.get("score", 0.0),
                    relevance_score=relevance_score,
                    explanation=explanation,
                    source=chunk.get("source", "unknown"),
                )
            )

    # Sort by relevance score (descending), then by original score
    scored_chunks.sort(
        key=lambda x: (x.relevance_score, x.original_score), reverse=True
    )

    # Keep chunks that meet score threshold, up to max_chunks
    kept_chunks = [
        chunk for chunk in scored_chunks if chunk.relevance_score >= min_score
    ][:max_chunks]

    dropped_chunks = [chunk for chunk in scored_chunks if chunk not in kept_chunks]

    log.info(
        "rerank_complete",
        total_chunks=len(chunks),
        kept=len(kept_chunks),
        dropped=len(dropped_chunks),
        top_scores=[c.relevance_score for c in kept_chunks],
    )

    return kept_chunks, dropped_chunks
