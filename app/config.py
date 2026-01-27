# app/config.py
"""Configuration constants for the License Intelligence System."""

import os
from pathlib import Path

# Directory paths
RAW_DATA_DIR = Path("data/raw")
TEXT_DATA_DIR = Path("data/text")
CHUNKS_DATA_DIR = Path("data/chunks")
CHROMA_DIR = Path("index/chroma")

# LLM Provider: "ollama" or "anthropic"
# Default is anthropic (Claude API) per spec v0.3; set LLM_PROVIDER=ollama for local-only
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Model configuration (Ollama)
LLM_MODEL = "llama3.2:8b"  # Use 8B for limited RAM; upgrade to 70b with more memory
EMBED_MODEL = "nomic-embed-text"

# Model configuration (Anthropic)
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"  # Latest Sonnet, active until Sep 2026+

# Chunking parameters (spec: 500-800 words target, 100-150 overlap, 100 min)
# Using lower values to stay within embedding model context limits
CHUNK_SIZE = 500  # words (spec: 500-800)
CHUNK_OVERLAP = 100  # words (spec: 100-150)
MIN_CHUNK_SIZE = 100  # words (spec: 100)
MAX_CHUNK_CHARS = 6000  # hard limit to prevent embedding overflow

# Retrieval parameters
TOP_K = 5

# Provider configuration
PROVIDERS: dict[str, dict[str, str]] = {
    "cme": {
        "name": "CME Group",
        "collection": "cme_docs",
    },
}

# Default provider for queries
DEFAULT_PROVIDERS = ["cme"]
