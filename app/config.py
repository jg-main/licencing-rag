# app/config.py

RAW_DATA_DIR = "data/raw"
TEXT_DATA_DIR = "data/text"
CHROMA_DIR = "index/chroma"

LLM_MODEL = "llama3.1:8b"
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 800  # words
CHUNK_OVERLAP = 120  # words
TOP_K = 5
