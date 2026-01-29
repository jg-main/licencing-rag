# app/audit.py
"""Query/response audit logging for compliance and usage tracking.

This module provides always-on audit logging separate from debug mode:
- Debug mode: verbose pipeline transparency for troubleshooting
- Audit logging: concise compliance/usage tracking for production

Audit logs capture:
- Query text and answers
- Sources and token usage
- Latency and refusal tracking
- Future: user_id for API authentication
"""

import json
import sys
import time
from datetime import datetime
from datetime import timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from app.logging import get_logger

log = get_logger(__name__)

# Global file handler for audit logs (initialized on first use)
_audit_file_handler: RotatingFileHandler | None = None


def get_audit_file_handler() -> RotatingFileHandler:
    """Get or create the rotating file handler for audit logs.

    Returns:
        RotatingFileHandler instance for queries.jsonl.
    """
    global _audit_file_handler

    if _audit_file_handler is not None:
        return _audit_file_handler

    from app.config import AUDIT_LOG_BACKUP_COUNT
    from app.config import AUDIT_LOG_FILE
    from app.config import AUDIT_LOG_MAX_BYTES
    from app.config import LOGS_DIR

    # Ensure logs directory exists
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create rotating file handler
    _audit_file_handler = RotatingFileHandler(
        filename=str(AUDIT_LOG_FILE),
        maxBytes=AUDIT_LOG_MAX_BYTES,
        backupCount=AUDIT_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )

    log.info(
        "audit_log_initialized",
        file=str(AUDIT_LOG_FILE),
        max_bytes=AUDIT_LOG_MAX_BYTES,
        backups=AUDIT_LOG_BACKUP_COUNT,
    )

    return _audit_file_handler


def _reset_handler() -> None:
    """Reset the global file handler (for testing purposes only)."""
    global _audit_file_handler
    if _audit_file_handler is not None:
        _audit_file_handler.close()
    _audit_file_handler = None


def log_query_response(
    query: str,
    answer: str,
    sources: list[str],
    chunks_retrieved: int,
    chunks_used: int,
    tokens_input: int,
    tokens_output: int,
    latency_ms: int,
    refused: bool = False,
    refusal_reason: str | None = None,
    user_id: str | None = None,
    write_to_console: bool = False,
) -> None:
    """Log query/response for compliance and usage tracking.

    This function ALWAYS logs to file (compliance requirement).
    Console output is optional via write_to_console parameter.

    Args:
        query: Original user query.
        answer: LLM response or refusal message.
        sources: List of data sources queried.
        chunks_retrieved: Number of chunks retrieved from search.
        chunks_used: Number of chunks used after reranking/budget.
        tokens_input: Prompt tokens sent to LLM.
        tokens_output: Completion tokens received from LLM.
        latency_ms: Total query processing time in milliseconds.
        refused: Whether the query was refused.
        refusal_reason: Reason for refusal (if refused).
        user_id: User identifier for API requests (null for CLI).
        write_to_console: If True, also write to console (stderr).
    """
    try:
        # Build audit log entry
        audit_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "answer": answer,
            "sources": sources,
            "chunks_retrieved": chunks_retrieved,
            "chunks_used": chunks_used,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "latency_ms": latency_ms,
            "refused": refused,
            "refusal_reason": refusal_reason,
            "user_id": user_id,
        }

        # ALWAYS write to audit log file (compliance requirement)
        handler = get_audit_file_handler()
        jsonl_line = json.dumps(audit_entry, ensure_ascii=False)
        handler.stream.write(jsonl_line + "\n")
        handler.stream.flush()

        # Optionally write to console (stderr)
        if write_to_console:
            # Pretty-print for human readability
            json_output = json.dumps(audit_entry, indent=2, ensure_ascii=False)
            print("\n" + "=" * 80, file=sys.stderr)
            print("AUDIT LOG", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            print(json_output, file=sys.stderr)
            print("=" * 80 + "\n", file=sys.stderr)

        log.debug(
            "query_logged",
            query_length=len(query),
            answer_length=len(answer),
            latency_ms=latency_ms,
            refused=refused,
        )

    except Exception as e:
        # Don't fail the query if audit logging fails
        log.error("audit_log_failed", error=str(e))
        print(f"\nWarning: Failed to write audit log: {e}", file=sys.stderr)


def calculate_latency_ms(start_time: float) -> int:
    """Calculate elapsed time in milliseconds.

    Args:
        start_time: Start time from time.time().

    Returns:
        Elapsed time in milliseconds as integer.
    """
    elapsed = time.time() - start_time
    return int(elapsed * 1000)
