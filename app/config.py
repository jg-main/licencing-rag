# app/config.py
"""Configuration constants for the License Intelligence System.

This module defines all configuration for the OpenAI-based RAG system.
Single source architecture: OpenAI only (no Ollama, no Claude).
"""

import os
from pathlib import Path

# Directory paths
RAW_DATA_DIR = Path("data/raw")
TEXT_DATA_DIR = Path("data/text")
CHUNKS_DATA_DIR = Path("data/chunks")
CHROMA_DIR = Path("index/chroma")
LOGS_DIR = Path("logs")

# Debug logging configuration (Phase 8.1)
DEBUG_LOG_ENABLED = True  # Write debug output to log files
DEBUG_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per log file
DEBUG_LOG_BACKUP_COUNT = 5  # Keep 5 rotated log files
DEBUG_LOG_FILE = LOGS_DIR / "debug.jsonl"  # JSON Lines format for easy parsing

# Query/Response Audit Logging (Phase 8.2 - always-on for compliance)
AUDIT_LOG_FILE = LOGS_DIR / "queries.jsonl"
AUDIT_LOG_MAX_BYTES = 50 * 1024 * 1024  # 50MB per log file
AUDIT_LOG_BACKUP_COUNT = 10  # Keep 10 old files (500MB total)

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# OpenAI Model Configuration (Single Provider - Breaking Change from v0.3)
EMBEDDING_MODEL = "text-embedding-3-large"  # 3072 dimensions
EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large output dimensions
LLM_MODEL = "gpt-4.1"  # For answer generation and reranking

# Chunking parameters (spec: 500-800 words target, 100-150 overlap, 100 min)
CHUNK_SIZE = 500  # words (spec: 500-800)
CHUNK_OVERLAP = 100  # words (spec: 100-150)
MIN_CHUNK_SIZE = 100  # words (spec: 100)
MAX_CHUNK_CHARS = 8000  # Increased for OpenAI's larger context window

# Retrieval parameters
TOP_K = 10  # Default chunks to retrieve (increased for better fee table coverage)

# Reranking parameters (Phase 4)
MAX_CHUNK_LENGTH_FOR_RERANKING = 2000  # Truncate chunks to this length for scoring
MIN_RERANKING_SCORE = (
    2  # Keep all chunks scoring >= this (2=RELEVANT, 3=HIGHLY RELEVANT)
)
MAX_CHUNKS_AFTER_RERANKING = 8  # Safety cap (balance: accuracy vs cost/context)
RERANKING_TIMEOUT = 30  # Timeout in seconds per chunk scoring (prevents hangs)
RERANKING_INCLUDE_EXPLANATIONS = False  # Include explanations (costs ~50% more tokens)
RERANKING_ENABLED = True  # Enable LLM reranking by default

# Context Budget parameters (Phase 5)
MAX_CONTEXT_TOKENS = (
    60000  # Hard limit: complete prompt (system + user) must be ≤60k tokens
)
CONTEXT_BUDGET_ENABLED = True  # Enable token budget enforcement

# Note: We no longer use static overhead estimates. Budget enforcement measures
# the FULL prompt (system + QA template + question + definitions + context) with
# tiktoken to guarantee the 60k limit. This is the accuracy-first approach.

# Confidence Gating parameters (Phase 6)
CONFIDENCE_GATE_ENABLED = True  # Enable confidence gating by default

# Reranking-based gating (0-3 scale)
RELEVANCE_THRESHOLD = 2  # Minimum relevance score (2=RELEVANT, 3=HIGHLY RELEVANT)
MIN_CHUNKS_REQUIRED = 1  # Minimum chunks above threshold to proceed

# Retrieval-score gating (when reranking disabled or fallback)
RETRIEVAL_MIN_SCORE = (
    0.05  # Top chunk must exceed minimum (prevents weak positives like 0.0001)
)
RETRIEVAL_MIN_RATIO = 1.2  # Top-1 score must be >= 1.2 × top-2 score (clear winner)

# Source configuration
SOURCES: dict[str, dict[str, str]] = {
    "cme": {
        "name": "CME Group",
        "collection": "cme_docs",
    },
}

# Default source for queries
DEFAULT_SOURCES = ["cme"]
