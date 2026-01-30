# Document Ingestion Guide

This guide explains how the License Intelligence System loads, processes, and indexes documents.

## Overview

Ingestion transforms raw PDF/DOCX files into searchable chunks with embeddings:

```
data/raw/{source}/**/*.pdf
    ↓ Extract
data/text/{source}/
    ↓ Chunk
data/chunks/{source}/
    ↓ Embed + Index
index/chroma/{source}_docs/
index/bm25/{source}_index.pkl
index/definitions/{source}_defs.pkl
```

## Command

```bash
# Ingest all documents for a source
rag ingest --source cme

# Re-ingest (rebuilds entire index)
rag ingest --source cme
```

## Pipeline Stages

### 1. Document Discovery

- Recursively scans `data/raw/{source}/` for `.pdf` and `.docx` files
- Supports nested subdirectories (e.g., `Fees/`, `Agreements/`)
- Deterministic ordering by relative path
- Skips hidden files (starting with `.`)

### 2. Text Extraction

**PDF Extraction (PyMuPDF):**

- Extracts text layer from PDF (no OCR)
- Tracks page numbers for each text segment
- Detects document version from metadata
- Validates extraction quality

**DOCX Extraction (python-docx):**

- Extracts paragraphs with run-level formatting
- Preserves headings and structure
- Tracks page estimates

**Output:**

```
data/text/cme/
├── Fees__january-2025-fee-list.pdf.txt
├── Fees__january-2025-fee-list.pdf.meta.json
└── ...
```

**Metadata includes:**

- Source file path
- Page count
- Extraction timestamp
- Document version
- Quality metrics (text length, page coverage)

### 3. Document Chunking

**Algorithm:**

- **Target size:** 500-800 words per chunk
- **Overlap:** 100 words between adjacent chunks
- **Section-aware:** Preserves document structure (headings, paragraphs)
- **Metadata preservation:** Each chunk carries full provenance

**Chunk Metadata:**

```python
{
    "chunk_id": "cme__Fees__schedule-a.pdf__chunk_0",
    "source": "cme",
    "document_path": "Fees/schedule-a.pdf",
    "section": "Section 3.1 Pricing",
    "page_start": 5,
    "page_end": 6,
    "is_definitions": False,  # True if chunk contains definitions
    "word_count": 650,
    "char_count": 4200
}
```

**Output:**

```
data/chunks/cme/
├── Fees__schedule-a.pdf.chunks.jsonl
├── Fees__schedule-a.pdf.chunks.meta.json
└── ...
```

### 4. Embedding Generation

**Model:** OpenAI `text-embedding-3-large` (3072 dimensions)

**Process:**

- Batch embeds chunks (100 at a time for efficiency)
- Retries on rate limits with exponential backoff
- Caches embeddings to avoid re-computation

**Cost:** ~$0.13 per 1M tokens (~$0.002 per document)

### 5. Vector Indexing (ChromaDB)

**Collection structure:**

- One collection per source: `{source}_docs` (e.g., `cme_docs`)
- Distance metric: Cosine similarity
- HNSW index for fast nearest-neighbor search

**Stored data:**

- Chunk text (for retrieval)
- 3072-dim embeddings (for search)
- Full metadata (for citations)

**Storage location:** `index/chroma/`

### 6. Keyword Indexing (BM25)

**Algorithm:** BM25 (Best Matching 25)

**Parameters:**

- `k1=1.5` (term frequency saturation)
- `b=0.75` (length normalization)

**Process:**

- Tokenizes chunk text
- Builds inverted index
- Computes IDF (inverse document frequency) scores

**Storage:** `index/bm25/{source}_index.pkl` (pickled Python object)

### 7. Definitions Indexing

**Purpose:** Auto-link defined terms to their definitions

**Process:**

1. Identifies chunks containing definitions (regex patterns)
1. Extracts term-definition pairs
1. Builds searchable index keyed by term
1. Caches for fast lookup

**Patterns detected:**

- `"Term" means ...`
- `"Term" shall mean ...`
- Definitions sections/schedules

**Storage:** `index/definitions/{source}_defs.pkl`

## Directory Structure

```
data/
├── raw/                    # Source documents (input)
│   └── cme/
│       ├── Fees/
│       │   └── schedule-a.pdf
│       └── Agreements/
│           └── main-agreement.pdf
├── text/                   # Extracted text (intermediate)
│   └── cme/
│       ├── Fees__schedule-a.pdf.txt
│       └── Agreements__main-agreement.pdf.txt
└── chunks/                 # Chunked documents (intermediate)
    └── cme/
        ├── Fees__schedule-a.pdf.chunks.jsonl
        └── Agreements__main-agreement.pdf.chunks.jsonl

index/
├── chroma/                 # Vector database (output)
│   └── cme_docs/
├── bm25/                   # Keyword index (output)
│   └── cme_index.pkl
└── definitions/            # Definitions index (output)
    └── cme_defs.pkl
```

## Re-Ingestion

**When to re-ingest:**

- Documents added or removed
- Documents updated
- Index corruption
- Embedding model change

**Process:**

```bash
# Full re-ingest (deletes old index)
rag ingest --source cme

# Manual cleanup first (optional)
rm -rf index/chroma/cme_docs
rm index/bm25/cme_index.pkl
rm index/definitions/cme_defs.pkl
rag ingest --source cme
```

**What happens:**

1. Deletes existing ChromaDB collection
1. Deletes BM25 and definitions indices
1. Re-runs full pipeline (extract, chunk, embed, index)

## Performance

**Typical ingestion time:**

- **Small doc** (10 pages): ~10 seconds
- **Medium doc** (50 pages): ~30 seconds
- **Large doc** (200 pages): ~2 minutes
- **Full source** (50 docs): ~5 minutes

**Bottlenecks:**

- PDF extraction (CPU-bound)
- Embedding generation (API rate limits)
- ChromaDB insertion (I/O-bound)

**Optimization tips:**

- Use batch embedding (already implemented)
- Upgrade OpenAI tier for higher rate limits
- Use SSD for ChromaDB storage

## Troubleshooting

### "No documents found"

**Cause:** Empty or invalid `data/raw/{source}/` directory

**Solution:**

```bash
# Check directory exists and has files
ls data/raw/cme/

# Ensure files are .pdf or .docx (case-insensitive)
```

### "Extraction failed"

**Cause:** Corrupted PDF or scanned PDF without text layer

**Solution:**

```bash
# Check if PDF is text-based
pdftotext document.pdf - | head

# If empty, PDF is scanned (OCR not supported)
```

### "Rate limit exceeded"

**Cause:** Too many OpenAI API requests

**Solution:**

- Wait 60 seconds and retry
- Upgrade API tier: [platform.openai.com/account/rate-limits](https://platform.openai.com/account/rate-limits)
- Reduce batch size in `app/config.py`

### "ChromaDB collection already exists"

**Cause:** Previous ingestion not cleaned up

**Solution:**

```bash
# Delete old collection
rm -rf index/chroma/cme_docs

# Re-ingest
rag ingest --source cme
```

## Best Practices

1. **Organize documents** - Use subdirectories for clarity (`Fees/`, `Agreements/`)
1. **Text-based PDFs only** - Verify documents have text layer
1. **Consistent naming** - Use descriptive filenames
1. **Version control** - Track document changes in `data-sources.md`
1. **Test after ingest** - Query a known fact to verify indexing

## Advanced: Incremental Ingestion

**Not currently supported.** Re-ingestion rebuilds the entire index.

**Future enhancement:** Track document hashes to skip unchanged files.

## See Also

- [Configuration Guide](configuration.md) - Chunking and embedding settings
- [Hybrid Search Guide](hybrid-search.md) - How indices are used
- [Data Sources](data-sources.md) - Document tracking
