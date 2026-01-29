# app/debug.py
"""Debug and audit mode for the License Intelligence System.

Phase 8 Implementation: Comprehensive Debug Output
- Full pipeline visibility for accuracy verification
- JSON output to stderr for separation from answer
- JSONL log files with rotation for audit trail
- All relevant metadata for auditing and troubleshooting
- Supports the accuracy-first principle through transparency
"""

import json
import sys
from datetime import datetime
from datetime import timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from app.logging import get_logger

log = get_logger(__name__)

# Global file handler for debug logs (initialized on first use)
_debug_file_handler: RotatingFileHandler | None = None


def get_debug_file_handler() -> RotatingFileHandler | None:
    """Get or create the rotating file handler for debug logs.

    Returns:
        RotatingFileHandler instance, or None if logging is disabled.
    """
    global _debug_file_handler

    if _debug_file_handler is not None:
        return _debug_file_handler

    try:
        from app.config import DEBUG_LOG_BACKUP_COUNT
        from app.config import DEBUG_LOG_ENABLED
        from app.config import DEBUG_LOG_FILE
        from app.config import DEBUG_LOG_MAX_BYTES
        from app.config import LOGS_DIR

        if not DEBUG_LOG_ENABLED:
            return None

        # Create logs directory if it doesn't exist
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        _debug_file_handler = RotatingFileHandler(
            DEBUG_LOG_FILE,
            maxBytes=DEBUG_LOG_MAX_BYTES,
            backupCount=DEBUG_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )

        log.info(
            "debug_log_handler_initialized",
            log_file=str(DEBUG_LOG_FILE),
            max_bytes=DEBUG_LOG_MAX_BYTES,
            backup_count=DEBUG_LOG_BACKUP_COUNT,
        )

        return _debug_file_handler

    except Exception as e:
        log.error("debug_log_handler_init_failed", error=str(e))
        return None


def write_debug_output(
    debug_data: dict[str, Any], write_to_stderr: bool = True
) -> None:
    """Write debug information to stderr and/or log file.

    ALWAYS writes to stderr when called (if write_to_stderr=True).
    File logging is gated by DEBUG_LOG_ENABLED config.

    This ensures --debug flag always shows output even if file logging is disabled.

    This function outputs comprehensive debug information to:
    1. stderr (if write_to_stderr=True) - ALWAYS (not gated by DEBUG_LOG_ENABLED)
    2. Rotating log file (logs/debug.jsonl) - only if DEBUG_LOG_ENABLED=True

    This allows:
    - Piping answer to file while seeing debug info
    - Permanent audit trail with rotation (optional)
    - Full pipeline transparency for accuracy verification

    Args:
        debug_data: Dictionary containing all debug information from query pipeline.
        write_to_stderr: If True, also write formatted output to stderr.
    """
    try:
        # Add timestamp to debug data
        timestamped_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **debug_data,
        }

        # ALWAYS write to stderr if requested (not gated by DEBUG_LOG_ENABLED)
        # This ensures --debug flag always shows output even if file logging is disabled
        if write_to_stderr:
            json_output = json.dumps(timestamped_data, indent=2, ensure_ascii=False)
            print("\n" + "=" * 80, file=sys.stderr)
            print("DEBUG OUTPUT (accuracy audit trail)", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            print(json_output, file=sys.stderr)
            print("=" * 80 + "\n", file=sys.stderr)

        # Write to log file (gated by DEBUG_LOG_ENABLED)
        handler = get_debug_file_handler()
        if handler is not None:
            try:
                # Compact JSON for JSONL format (one line per entry)
                jsonl_line = json.dumps(timestamped_data, ensure_ascii=False)
                handler.stream.write(jsonl_line + "\n")
                handler.stream.flush()
            except Exception as file_err:
                log.error("debug_file_write_failed", error=str(file_err))

    except Exception as e:
        log.error("debug_output_failed", error=str(e))
        # Don't fail the query if debug output fails
        print(f"\nWarning: Failed to write debug output: {e}", file=sys.stderr)


def build_debug_output(
    original_query: str,
    normalized_query: str,
    normalization_applied: bool,
    normalization_failed: bool,
    sources: list[str],
    search_mode: str,
    effective_search_mode: str,
    retrieval_info: dict[str, Any] | None = None,
    reranking_info: dict[str, Any] | None = None,
    confidence_gate_info: dict[str, Any] | None = None,
    budget_info: dict[str, Any] | None = None,
    final_chunks_count: int = 0,
    final_context_tokens: int | None = None,
    definitions_count: int = 0,
    llm_called: bool = True,
    validation_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build comprehensive debug output dictionary.

    This function aggregates all debug information from the query pipeline
    into a structured format for auditability and troubleshooting.

    Args:
        original_query: User's original question.
        normalized_query: Normalized query used for retrieval.
        normalization_applied: Whether normalization changed the query.
        normalization_failed: Whether normalization produced empty string.
        sources: List of sources queried.
        search_mode: Requested search mode.
        effective_search_mode: Actual search mode used (may differ due to fallback).
        retrieval_info: Information about chunk retrieval per source.
        reranking_info: Information about LLM reranking (Phase 4).
        confidence_gate_info: Information about confidence gating (Phase 6).
        budget_info: Information about context budget enforcement (Phase 5).
        final_chunks_count: Number of chunks in final context.
        final_context_tokens: Total tokens in final context.
        definitions_count: Number of auto-linked definitions.
        llm_called: Whether LLM was called for answer generation.
        validation_info: Information about output validation (Phase 7).

    Returns:
        Structured debug dictionary ready for JSON serialization.
    """
    debug_output: dict[str, Any] = {
        # Phase 2: Query Normalization
        "query_processing": {
            "original_query": original_query,
            "normalized_query": normalized_query,
            "normalization_applied": normalization_applied,
            "normalization_failed": normalization_failed,
            "changes": (
                _describe_normalization_changes(original_query, normalized_query)
                if normalization_applied
                else None
            ),
        },
        # Phase 3: Hybrid Retrieval
        "retrieval": {
            "sources_queried": sources,
            "search_mode_requested": search_mode,
            "search_mode_effective": effective_search_mode,
            "fallback_occurred": search_mode != effective_search_mode,
            "per_source_results": retrieval_info or {},
        },
        # Phase 4: LLM Reranking
        "reranking": reranking_info or {"enabled": False},
        # Phase 6: Confidence Gating
        "confidence_gate": confidence_gate_info or {"enabled": False},
        # Phase 5: Context Budget
        "budget": budget_info or {"enabled": False},
        # Final Context Summary
        "final_context": {
            "chunks_count": final_chunks_count,
            "tokens_count": final_context_tokens,
            "definitions_count": definitions_count,
            "llm_called": llm_called,
        },
        # Phase 7: Output Validation
        "validation": validation_info or {},
    }

    return debug_output


def _describe_normalization_changes(original: str, normalized: str) -> dict[str, Any]:
    """Describe what changed during normalization.

    Args:
        original: Original query string.
        normalized: Normalized query string.

    Returns:
        Dictionary describing the changes.
    """
    original_words = original.lower().split()
    normalized_words = normalized.lower().split()

    removed_words = [w for w in original_words if w not in normalized_words]
    added_words = [w for w in normalized_words if w not in original_words]

    return {
        "removed_words": removed_words,
        "added_words": added_words,
        "length_change": len(normalized) - len(original),
        "word_count_change": len(normalized_words) - len(original_words),
    }


def format_retrieval_info(
    all_search_results: list[dict[str, Any]], sources: list[str]
) -> dict[str, Any]:
    """Format retrieval information for debug output.

    Args:
        all_search_results: List of all retrieved chunks with scores.
        sources: List of sources queried.

    Returns:
        Dictionary with per-source retrieval statistics.
    """
    per_source: dict[str, dict[str, Any]] = {}

    for source in sources:
        source_chunks = [r for r in all_search_results if r["source"] == source]

        if source_chunks:
            per_source[source] = {
                "chunks_retrieved": len(source_chunks),
                "top_scores": [
                    round(c["score"], 4)
                    for c in sorted(
                        source_chunks, key=lambda x: x["score"], reverse=True
                    )[:5]
                ],
                "avg_score": round(
                    sum(c["score"] for c in source_chunks) / len(source_chunks), 4
                ),
                "retrieval_methods": list(
                    set(c.get("method", "unknown") for c in source_chunks)
                ),
            }
        else:
            per_source[source] = {
                "chunks_retrieved": 0,
                "top_scores": [],
                "avg_score": 0.0,
                "retrieval_methods": [],
            }

    total_chunks = sum(info["chunks_retrieved"] for info in per_source.values())

    return {
        "total_chunks": total_chunks,
        "per_source": per_source,
    }
