# app/config.py
"""Configuration constants for the License Intelligence System.

This module defines all configuration for the OpenAI-based RAG system.
Single provider architecture: OpenAI only (no Ollama, no Claude).
"""

import os
from pathlib import Path

# Directory paths
RAW_DATA_DIR = Path("data/raw")
TEXT_DATA_DIR = Path("data/text")
CHUNKS_DATA_DIR = Path("data/chunks")
CHROMA_DIR = Path("index/chroma")

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

# Provider configuration
PROVIDERS: dict[str, dict[str, str]] = {
    "cme": {
        "name": "CME Group",
        "collection": "cme_docs",
    },
}

# Default provider for queries
DEFAULT_PROVIDERS = ["cme"]
