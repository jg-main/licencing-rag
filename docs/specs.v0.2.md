# CME License Intelligence System (Local RAG) - Technical Product Brief

**Project Name:** License Intelligence System (Local RAG) **Version:** 0.2 **Last Updated:** 2026-01-26

## Changelog from v0.1

- Added multi-provider architecture (CME, OPRA, CTA/UTP)
- Clarified ChromaDB usage patterns (PersistentClient)
- Added page number tracking for citations
- Defined metadata schema explicitly
- Added CLI interface specification
- Clarified embedding function requirements

______________________________________________________________________

## 1. Objective

Build a **local, private legal Q&A system** that answers questions **exclusively** based on curated license agreements and exhibits from multiple market data providers.

### Supported Providers (Current & Planned)

| Provider  | Status  | Document Count |
| --------- | ------- | -------------- |
| CME Group | Active  | ~35 documents  |
| OPRA      | Planned | TBD            |
| CTA/UTP   | Planned | TBD            |

The system must:

- Respond **only** using the provided documents
- Explicitly refuse to answer when the documents are silent
- Always provide **citations** (provider, document name, section, page)
- Use Claude API for answer generation (with local Ollama as fallback option)
- Use local embeddings via Ollama (nomic-embed-text)
- Be maintainable as documents are updated
- Support querying across providers or within a specific provider

This is **not** a general chatbot and **not** a trained LLM. It is a **retrieval-grounded legal analysis tool**.

______________________________________________________________________

## 2. Non-Goals (Explicitly Out of Scope)

- No model training or fine-tuning
- No external data sources (documents are curated locally)
- No web scraping or internet content retrieval
- No legal advice generation beyond document interpretation
- No "best practice" or industry commentary unless explicitly stated in the documents
- No cross-provider comparison or harmonization (Phase 1)

______________________________________________________________________

## 3. High-Level Architecture

The system follows a **Retrieval-Augmented Generation (RAG)** pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Document Ingestion Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│  data/raw/{provider}/*.pdf  →  Extract  →  Chunk  →  Embed     │
│                                   ↓                              │
│                          data/text/{provider}/                   │
│                                   ↓                              │
│                          index/chroma/                           │
│                     (collection per provider)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Query Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  User Question  →  Embed  →  Vector Search  →  Top-K Chunks     │
│                                                    ↓             │
│                              LLM Prompt (context + question)     │
│                                                    ↓             │
│                              Answer + Citations                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **One ChromaDB collection per provider** — Enables provider-specific queries and simpler re-ingestion
1. **Unified query interface** — Can search all providers or filter to specific ones
1. **Metadata-rich chunks** — Every chunk carries full provenance for citation

______________________________________________________________________

## 4. Technology Stack

### Runtime

- Python 3.13+
- Local execution on developer machine (macOS / Windows / Linux)

### Models

| Purpose        | Model              | Notes                                              |
| -------------- | ------------------ | -------------------------------------------------- |
| LLM (Primary)  | Claude Sonnet 4    | Via Anthropic API, reasoning and answer generation |
| LLM (Fallback) | `llama3.1:8b`      | Local via Ollama, for offline use                  |
| Embeddings     | `nomic-embed-text` | Local via Ollama, 768-dim vectors                  |

### Libraries

| Library       | Purpose                   | Version |
| ------------- | ------------------------- | ------- |
| `anthropic`   | Claude API (primary LLM)  | 0.76+   |
| `ollama`      | Embeddings + fallback LLM | 0.6+    |
| `chromadb`    | Vector database           | 1.4+    |
| `pymupdf`     | PDF text extraction       | 1.26+   |
| `python-docx` | DOCX text extraction      | 1.2+    |
| `rich`        | Console output formatting | 14.0+   |
| `tqdm`        | Progress bars             | 4.67+   |
| `structlog`   | Structured logging        | 25.0+   |

### LLM Provider Configuration

The system uses Claude API by default for answer generation:

```bash
export LLM_PROVIDER="anthropic"  # default
export ANTHROPIC_API_KEY="sk-ant-..."
```

For offline or local-only execution, switch to Ollama:

```bash
export LLM_PROVIDER="ollama"
```

**Note:** Embeddings always use local Ollama (nomic-embed-text) regardless of LLM provider.

______________________________________________________________________

## 5. Directory Structure

```
licencing-rag/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration constants
│   ├── extract.py          # PDF/DOCX text extraction
│   ├── chunking.py         # Document chunking logic
│   ├── ingest.py           # Ingestion pipeline
│   ├── query.py            # Query pipeline
│   └── prompts.py          # LLM prompts
├── data/
│   ├── raw/
│   │   ├── cme/            # CME source documents
│   │   ├── opra/           # OPRA source documents (future)
│   │   └── cta_utp/        # CTA/UTP source documents (future)
│   ├── text/
│   │   ├── cme/            # Extracted text files
│   │   ├── opra/
│   │   └── cta_utp/
│   └── chunks/
│       └── {provider}/     # Optional: serialized chunks for debugging
├── index/
│   └── chroma/             # ChromaDB persistent storage
├── docs/
│   ├── specs.v0.1.md
│   ├── specs.v0.2.md
│   └── implementation-plan.md
├── main.py                 # CLI entrypoint
├── makefile
├── pyproject.toml
└── README.md
```

______________________________________________________________________

## 6. Document Ingestion Requirements

### Supported Formats

| Format | Extractor   | Notes                          |
| ------ | ----------- | ------------------------------ |
| PDF    | PyMuPDF     | Native text extraction, no OCR |
| DOCX   | python-docx | Paragraph-based extraction     |

### Extraction Output

For each source document, produce:

1. **Clean text file** — `data/text/{provider}/{filename}.txt`
1. **Metadata JSON** — `data/text/{provider}/{filename}.meta.json`

Metadata JSON schema:

```json
{
  "source_file": "information-license-agreement-ila-guide.pdf",
  "provider": "cme",
  "extracted_at": "2026-01-26T10:30:00Z",
  "page_count": 42,
  "extraction_method": "pymupdf"
}
```

### Constraints

- OCR is out of scope (assume text-based PDFs)
- Manual verification of extraction quality is recommended for first batch

______________________________________________________________________

## 7. Chunking Strategy

### Chunk Parameters

| Parameter   | Value         | Rationale                     |
| ----------- | ------------- | ----------------------------- |
| Target size | 500-800 words | Balance context vs. precision |
| Overlap     | 100-150 words | Preserve clause continuity    |
| Min chunk   | 100 words     | Avoid tiny fragments          |

### Chunk Boundaries (Priority Order)

1. Section headers (e.g., `SECTION 7`, `Article III`, `2.03`)
1. Exhibit/Schedule breaks
1. Paragraph breaks
1. Word-count window (fallback)

### Section Detection Patterns

```python
SECTION_PATTERNS = [
    r"^SECTION\s+\d+",
    r"^Article\s+[IVXLCDM]+",
    r"^ARTICLE\s+\d+",
    r"^\d+\.\d+(\.\d+)?",
    r"^EXHIBIT\s+[A-Z]",
    r"^SCHEDULE\s+\d+",
    r"^APPENDIX\s+[A-Z]",
]
```

### Metadata Schema (Per Chunk)

```python
{
    "chunk_id": str,           # Unique: "{provider}_{filename}_{index}"
    "provider": str,           # "cme", "opra", "cta_utp"
    "document_name": str,      # Source filename
    "document_version": str,   # If detectable (e.g., "v5.0")
    "section_heading": str,    # Detected section title or "N/A"
    "page_start": int,         # Starting page number (1-indexed)
    "page_end": int,           # Ending page number
    "chunk_index": int,        # Position within document
    "word_count": int,         # Actual word count
}
```

### Definitions Handling

- Chunks containing "Definitions" or "Defined Terms" in heading get tagged: `"is_definitions": true`
- Future: Auto-retrieve definition chunks when clauses reference quoted terms

______________________________________________________________________

## 8. Vector Database Schema

### ChromaDB Configuration

```python
import chromadb

client = chromadb.PersistentClient(path="index/chroma")

# One collection per provider
cme_collection = client.get_or_create_collection(
    name="cme_docs",
    metadata={"provider": "cme"},
    embedding_function=ollama_embedding_function,
)
```

### Embedding Function

```python
import ollama

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts using Ollama nomic-embed-text."""
    embeddings = []
    for text in texts:
        response = ollama.embed(model="nomic-embed-text", input=text)
        embeddings.append(response["embeddings"][0])
    return embeddings
```

______________________________________________________________________

## 9. Query Pipeline

### Query Flow

1. Parse user question
1. Optionally filter by provider(s)
1. Embed question using same embedding model
1. Retrieve top-k chunks from relevant collection(s)
1. Construct prompt with retrieved context
1. Generate answer via LLM
1. Format response with citations

### Retrieval Parameters

| Parameter       | Default | Notes                                   |
| --------------- | ------- | --------------------------------------- |
| top_k           | 5       | Number of chunks to retrieve            |
| provider_filter | None    | Optional: limit to specific provider(s) |

### Answer Constraints (Hard Rules)

The LLM **must**:

- Use **only** the retrieved context
- Never rely on prior knowledge
- Never speculate or generalize
- Explicitly refuse if answer not found

Standard refusal:

> "This is not addressed in the provided {provider} documents."

______________________________________________________________________

## 10. Output Format

### Response Structure

```
## Answer

{Clear, concise answer grounded in documents}

## Supporting Clauses

> "{Quoted excerpt from document}"
> — {Document Name}, {Section}

## Citations

- **{Document Name}** (Page {X}): {Section heading}
- **{Document Name}** (Page {Y}): {Section heading}

## Notes

- {Any ambiguities or cross-references}
```

### Citation Format

Each citation must include:

- Provider name (if multi-provider query)
- Document filename
- Section heading or identifier
- Page number(s)

______________________________________________________________________

## 11. CLI Interface

### Commands

```bash
# Ingest documents for a provider
python main.py ingest --provider cme

# Ingest all providers
python main.py ingest --all

# Query with default settings
python main.py query "What are the redistribution requirements?"

# Query specific provider
python main.py query --provider cme "What fees apply to derived data?"

# Query multiple providers
python main.py query --provider cme --provider opra "Definition of subscriber"

# List indexed documents
python main.py list --provider cme
```

### Exit Codes

| Code | Meaning              |
| ---- | -------------------- |
| 0    | Success              |
| 1    | General error        |
| 2    | No documents found   |
| 3    | Provider not indexed |

______________________________________________________________________

## 12. Security & Privacy

- Fully local execution
- No telemetry
- No outbound network calls (except Ollama localhost)
- Vector DB stored locally with filesystem permissions
- Optional query logging for auditability

______________________________________________________________________

## 13. Success Criteria

The system is successful if:

| Criterion       | Measurement                                 |
| --------------- | ------------------------------------------- |
| Grounding       | Never answers beyond provided documents     |
| Citations       | Every answer includes document + section    |
| Refusal         | Correctly refuses when info not found       |
| Maintainability | Adding documents requires re-ingestion only |
| Performance     | \<10s response time on standard laptop      |
| Extensibility   | New provider added without code changes     |

______________________________________________________________________

## 14. Future Enhancements (Deferred)

| Enhancement                   | Priority | Notes                       |
| ----------------------------- | -------- | --------------------------- |
| CTA/UTP document ingestion    | Medium   | After OPRA                  |
| Hybrid search (BM25 + vector) | Medium   | Better keyword matching     |
| Definitions auto-linking      | Medium   | Auto-include defined terms  |
| Clause comparison             | Low      | Cross-document analysis     |
| Risk flag extraction          | Low      | Audit, termination triggers |
| Version diffing               | Low      | Compare document versions   |
| Web UI (Streamlit)            | Low      | After CLI is stable         |

______________________________________________________________________

## 15. Guiding Principles

1. **Correctness over fluency** — Precise, grounded answers beat eloquent speculation
1. **Traceability** — Every statement must cite its source
1. **Refusal is a feature** — Saying "not found" is a correct answer
1. **Simplicity** — Minimal dependencies, clear code, no magic
1. **Extensibility** — Adding providers should be configuration, not code surgery
