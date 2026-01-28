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

# Provider configuration
PROVIDERS: dict[str, dict[str, str]] = {
    "cme": {
        "name": "CME Group",
        "collection": "cme_docs",
    },
}

# Default provider for queries
DEFAULT_PROVIDERS = ["cme"]
