# app/config.py
"""Configuration constants for the License Intelligence System."""

from pathlib import Path

# Directory paths
RAW_DATA_DIR = Path("data/raw")
TEXT_DATA_DIR = Path("data/text")
CHROMA_DIR = Path("index/chroma")

# Model configuration
LLM_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"

# Chunking parameters
CHUNK_SIZE = 800  # words
CHUNK_OVERLAP = 120  # words
MIN_CHUNK_SIZE = 100  # words

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
