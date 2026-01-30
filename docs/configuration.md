# Configuration Guide

This document explains all configuration options for the License Intelligence System.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Application Configuration](#application-configuration)
- [ChromaDB Settings](#chromadb-settings)
- [Search Configuration](#search-configuration)
- [Reranking Settings](#reranking-settings)
- [Confidence Gating](#confidence-gating)
- [Context Budget](#context-budget)
- [Logging](#logging)

______________________________________________________________________

## Environment Variables

### Required

#### `OPENAI_API_KEY`

OpenAI API key for embeddings and LLM operations.

**Required:** Yes\
**Format:** `sk-...`\
**Get it from:** [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

**Usage:**

```bash
export OPENAI_API_KEY="sk-..."
```

**Docker:**

```bash
docker run -e OPENAI_API_KEY="sk-..." ...
```

### Optional

Currently, the system only requires the OpenAI API key. All other configuration is managed through `app/config.py` constants.

______________________________________________________________________

## Application Configuration

All configuration constants are defined in `app/config.py`. These can be modified for advanced use cases.

### Data Directories

```python
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
TEXT_DATA_DIR = PROJECT_ROOT / "data" / "text"
CHUNK_DATA_DIR = PROJECT_ROOT / "data" / "chunks"
```

- **`RAW_DATA_DIR`**: Source documents (PDF, DOCX, TXT) organized by provider (e.g., `data/raw/cme/`)
- **`TEXT_DATA_DIR`**: Extracted text files mirroring the raw structure
- **`CHUNK_DATA_DIR`**: Chunked documents in JSONL format with metadata

### Index Locations

```python
INDEX_DIR = PROJECT_ROOT / "index"
CHROMA_DIR = INDEX_DIR / "chroma"
BM25_DIR = INDEX_DIR / "bm25"
DEFINITIONS_DIR = INDEX_DIR / "definitions"
```

- **`CHROMA_DIR`**: ChromaDB vector database storage
- **`BM25_DIR`**: BM25 keyword search index (pickled)
- **`DEFINITIONS_DIR`**: Definitions index (pickled)

### Logging

```python
LOGS_DIR = PROJECT_ROOT / "logs"
DEBUG_LOG_FILE = LOGS_DIR / "debug.jsonl"
QUERY_LOG_FILE = LOGS_DIR / "queries.jsonl"
```

- **`DEBUG_LOG_FILE`**: Debug output in JSONL format (10MB max, 5 backups)
- **`QUERY_LOG_FILE`**: Query audit logs in JSONL format (50MB max, 10 backups)

______________________________________________________________________

## ChromaDB Settings

### Embedding Model

```python
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 3072
```

**Note:** If you change the embedding model, you **must** delete the existing index and re-ingest:

```bash
rm -rf index/chroma/
rag ingest --source cme
```

### Collection Naming

```python
# Format: {source}_docs
# Example: cme_docs, opra_docs
```

Each data source gets its own ChromaDB collection. This enables multi-source queries.

______________________________________________________________________

## Search Configuration

### Retrieval Settings

```python
# Default number of chunks to retrieve per source
TOP_K_RETRIEVAL = 10

# Maximum candidates before reranking (vector + BM25)
MAX_RETRIEVAL_CANDIDATES = 12
```

### Search Modes

Available via `--search-mode` CLI flag:

| Mode      | Description                      | Use When                    |
| --------- | -------------------------------- | --------------------------- |
| `hybrid`  | Vector + BM25 with RRF (default) | Best overall accuracy       |
| `vector`  | OpenAI embeddings only           | Semantic/conceptual queries |
| `keyword` | BM25 only                        | Exact phrase matching       |

**Example:**

```bash
rag query "What is CME?" --search-mode hybrid
```

______________________________________________________________________

## Reranking Settings

### LLM Reranking Configuration

```python
LLM_MODEL = "gpt-4.1"
RERANKING_INCLUDE_EXPLANATIONS = False  # Set True for debugging
RERANKING_MAX_WORKERS = 5  # Parallel API calls
RERANKING_TIMEOUT = 30  # Seconds per chunk
```

### Scoring Scale

Chunks are scored 0-3 by GPT-4.1:

| Score | Meaning                       |
| ----- | ----------------------------- |
| **3** | Directly answers the question |
| **2** | Provides relevant context     |
| **1** | Tangentially related          |
| **0** | Irrelevant                    |

### Thresholds

```python
RERANKING_MIN_SCORE = 2  # Keep chunks scoring ≥2
RERANKING_MAX_CHUNKS = 10  # Maximum chunks after reranking
```

**Optimization:** Single-token scoring saves ~50% on reranking costs. Enable explanations only for debugging:

```python
RERANKING_INCLUDE_EXPLANATIONS = True
```

______________________________________________________________________

## Confidence Gating

Confidence gating prevents hallucinations by refusing to answer when evidence is weak.

### Configuration

```python
RELEVANCE_THRESHOLD = 2  # Reranked scores must be ≥2
MIN_CHUNKS_REQUIRED = 1  # At least 1 high-quality chunk

# Retrieval score thresholds (when reranking disabled)
RETRIEVAL_MIN_SCORE = 0.05  # Absolute minimum
RETRIEVAL_MIN_RATIO = 1.2   # Top-1/top-2 must be >1.2
```

### How It Works

**After reranking:**

- Refuse if no chunk scores ≥2
- Refuse if top score \<2

**Without reranking:**

- Refuse if top score ≤0.05 (too weak)
- Refuse if top-1/top-2 ratio \<1.2 (no clear winner)

### Disabling (Not Recommended)

```bash
rag query "..." --no-gate
```

**Warning:** Disabling confidence gating increases hallucination risk.

______________________________________________________________________

## Context Budget

Enforces ≤60k token limit for LLM input to prevent truncation and maintain performance.

### Configuration

```python
MAX_CONTEXT_TOKENS = 60_000
```

### How It Works

1. After reranking, count tokens for all chunks + definitions
1. If over budget, drop lowest-scoring chunks first
1. Prefer shorter chunks when scores are tied
1. Refuse if no chunks remain after budget enforcement

### Disabling (Not Recommended)

```bash
rag query "..." --no-budget
```

**Warning:** Exceeding context limits may cause API errors or truncated prompts.

______________________________________________________________________

## Logging

### Levels

Controlled by the `--debug` flag:

```bash
# Normal mode (INFO level)
rag query "What is CME?"

# Debug mode (DEBUG level)
rag query "What is CME?" --debug
```

### Debug Output

When `--debug` is enabled:

- **stderr**: Real-time JSON debug output
- **`logs/debug.jsonl`**: Rotating log file (10MB max, 5 backups)

Debug output includes:

- Query normalization
- Retrieval statistics
- Reranking scores
- Confidence gate decisions
- Budget enforcement
- Token counts
- LLM prompts and responses

### Query Audit Logs

**Always enabled** for compliance:

- **`logs/queries.jsonl`**: All queries logged (50MB max, 10 backups)
- Optional stderr output: `rag query "..." --log-queries`

Log format:

```json
{
  "timestamp": "2026-01-30T16:00:00.000000+00:00",
  "query": "What is CME?",
  "answer": "...",
  "sources": ["cme"],
  "chunks_retrieved": 10,
  "chunks_used": 3,
  "tokens_input": 8500,
  "tokens_output": 450,
  "latency_ms": 3200,
  "refused": false
}
```

______________________________________________________________________

## Advanced Configuration

### Chunking Settings

```python
MIN_CHUNK_SIZE = 500  # Minimum words per chunk
MAX_CHUNK_SIZE = 800  # Maximum words per chunk
CHUNK_OVERLAP = 100   # Overlap between chunks (words)
```

### BM25 Configuration

```python
# rank-bm25 uses default parameters:
# k1 = 1.5 (term frequency saturation)
# b = 0.75 (length normalization)
```

### Definitions Auto-Linking

```python
# Automatically enabled
# Scans answer for quoted terms
# Retrieves definitions from index
```

______________________________________________________________________

## Configuration Best Practices

### For Production

1. **Always** set `OPENAI_API_KEY` environment variable
1. **Never** disable confidence gating (`--no-gate`)
1. **Never** disable budget enforcement (`--no-budget`)
1. Use `hybrid` search mode for best accuracy
1. Monitor `logs/queries.jsonl` for usage patterns
1. Enable `--debug` only for troubleshooting

### For Development

1. Use `--debug` to understand retrieval pipeline
1. Enable `RERANKING_INCLUDE_EXPLANATIONS = True` to see scoring rationale
1. Test with `--search-mode vector` and `--search-mode keyword` to compare
1. Check `logs/debug.jsonl` for detailed pipeline analysis

### For Cost Optimization

1. Reduce `TOP_K_RETRIEVAL` to retrieve fewer chunks
1. Keep `RERANKING_INCLUDE_EXPLANATIONS = False` (saves 50% on reranking)
1. Use vector-only search when appropriate (skips BM25)
1. Monitor token usage in `logs/queries.jsonl`

______________________________________________________________________

## Configuration Validation

To verify configuration:

```bash
# Test embeddings
rag query "test" --debug 2>&1 | grep embedding

# Check reranking settings
python3 -c "from app.config import *; print(f'Model: {LLM_MODEL}, Max tokens: {MAX_CONTEXT_TOKENS}')"

# Verify API key
python3 -c "import os; print('✓ API key set' if os.getenv('OPENAI_API_KEY') else '✗ API key missing')"
```

______________________________________________________________________

## Related Documentation

- [Ingestion Guide](ingestion.md) - How to load documents
- [Query Normalization](query-normalization.md) - How queries are preprocessed
- [Reranking](reranking.md) - How chunks are scored
- [Confidence Gating](confidence-gating.md) - How refusal decisions are made
- [Debug Mode](debug-mode.md) - How to troubleshoot issues
- [Cost Estimation](cost-estimation.md) - How to estimate API costs
