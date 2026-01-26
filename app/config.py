# app/config.py
"""Configuration constants for the License Intelligence System."""

import os
from pathlib import Path

# Directory paths
RAW_DATA_DIR = Path("data/raw")
TEXT_DATA_DIR = Path("data/text")
CHROMA_DIR = Path("index/chroma")

# LLM Provider: "ollama" or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Model configuration (Ollama)
LLM_MODEL = "llama3.2:8b"  # Use 8B for limited RAM; upgrade to 70b with more memory
EMBED_MODEL = "nomic-embed-text"

# Model configuration (Anthropic)
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"  # Latest Sonnet, active until Sep 2026+

# Chunking parameters
CHUNK_SIZE = 400  # words (reduced to stay within embedding context)
CHUNK_OVERLAP = 60  # words
MIN_CHUNK_SIZE = 50  # words
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
