# CME License Intelligence System (Local RAG) - Technical Product Brief

**Project Name:** License Intelligence System (Local RAG) **Version:** 0.3 **Last Updated:** 2026-01-27

## Changelog from v0.2

- **Promoted to Core Features**: Hybrid search, definitions auto-linking, query logging (formerly deferred)
- **Added**: REST API specifications (FastAPI)
- **Added**: Deployment specifications (Docker, AWS ECS/Fargate)
- **Added**: CI/CD pipeline requirements
- **Added**: Subdirectory support for document organization
- **Clarified**: Multi-provider architecture details
- **Updated**: Performance and scalability targets

______________________________________________________________________

## 1. Objective

Build a **local, private legal Q&A system** that answers questions **exclusively** based on curated license agreements and exhibits from multiple market data providers.

### Supported Data Provider (Current & Planned)

| Provider  | Status  | Document Count | Priority |
| --------- | ------- | -------------- | -------- |
| CME Group | Active  | ~35 documents  | P0       |
| OPRA      | Planned | TBD            | P1       |
| CTA/UTP   | Planned | TBD            | P2       |

### Supported LLM Providers (Current & Planned)

| Provider | Status     | Priority |
| -------- | ---------- | -------- |
| Claude   | Active     | N/A      |
| OpenAI   | Considered | Medium   |

The system must:

- Respond **only** using the provided documents
- Explicitly refuse to answer when the documents are silent
- Always provide **citations** (provider, document name, section, page)
- Use LLM API for answer generation (with local Ollama as fallback option)
- Use local embeddings via Ollama (nomic-embed-text)
- Support hybrid search (vector + keyword) for improved retrieval
- Auto-link defined terms to their definitions
- Log all queries for audit and analysis
- Provide REST API for programmatic access
- Be deployable to cloud infrastructure
- Be maintainable as documents are updated
- Support querying across providers or within a specific provider
- Support subdirectory organization (e.g., `Fees/`, `Agreements/`)

This is **not** a general chatbot and **not** a trained LLM. It is a **retrieval-grounded legal analysis tool**.

______________________________________________________________________

## 2. Non-Goals (Explicitly Out of Scope)

- No model training or fine-tuning
- No external data sources (documents are curated locally)
- No web scraping or internet content retrieval
- No legal advice generation beyond document interpretation
- No "best practice" or industry commentary unless explicitly stated in the documents
- No automated clause negotiation or contract generation
- No personal data collection or user tracking (beyond query logging for audit)

______________________________________________________________________

## 3. High-Level Architecture

The system follows a **Retrieval-Augmented Generation (RAG)** pattern with hybrid search:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Document Ingestion Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│  data/raw/{provider}/**/*.pdf  →  Extract  →  Chunk  →  Embed  │
│                                      ↓                           │
│                          data/text/{provider}/                   │
│                                      ↓                           │
│                          index/chroma/                           │
│                     (collection per provider)                    │
│                                      ↓                           │
│                          index/bm25/                             │
│                     (keyword index per provider)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Query Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  User Question  →  Embed  →  Vector Search (Top-K)              │
│                      ↓                                           │
│                  BM25 Search (Top-K)                             │
│                      ↓                                           │
│              Hybrid Ranking (RRF)  →  Top-N Chunks               │
│                      ↓                                           │
│         Definitions Auto-Linking (if needed)                     │
│                      ↓                                           │
│              LLM Prompt (context + question)                     │
│                      ↓                                           │
│              Answer + Citations                                  │
│                      ↓                                           │
│              Query Logging (logs/queries.jsonl)                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **One ChromaDB collection per provider** — Enables provider-specific queries and simpler re-ingestion
1. **Hybrid search** — Combines semantic (vector) and keyword (BM25) retrieval for better coverage
1. **Definitions auto-linking** — Automatically retrieves definition chunks when terms are referenced
1. **Unified query interface** — Can search all providers or filter to specific ones
1. **Metadata-rich chunks** — Every chunk carries full provenance for citation
1. **Subdirectory support** — Organize documents in folders (Fees/, Agreements/, etc.)
1. **Query logging** — All queries logged to JSONL for audit and analysis

______________________________________________________________________

## 4. Technology Stack

### Runtime

- Python 3.13+
- Local execution on developer machine (macOS / Windows / Linux)
- Docker for containerization (deployment)
- AWS ECS/Fargate for cloud deployment

### Models

| Purpose        | Model              | Notes                                              |
| -------------- | ------------------ | -------------------------------------------------- |
| LLM (Primary)  | Claude Sonnet 4.5  | Via Anthropic API, reasoning and answer generation |
| LLM (Fallback) | `llama3.1:8b`      | Local via Ollama, for offline use                  |
| Embeddings     | `nomic-embed-text` | Local via Ollama, 768-dim vectors                  |

### Libraries

| Library       | Purpose                   | Version |
| ------------- | ------------------------- | ------- |
| `anthropic`   | Claude API (primary LLM)  | 0.76+   |
| `ollama`      | Embeddings + fallback LLM | 0.6+    |
| `chromadb`    | Vector database           | 1.4+    |
| `rank-bm25`   | BM25 keyword search       | 0.2+    |
| `pymupdf`     | PDF text extraction       | 1.26+   |
| `python-docx` | DOCX text extraction      | 1.2+    |
| `fastapi`     | REST API framework        | 0.115+  |
| `uvicorn`     | ASGI server               | 0.32+   |
| `rich`        | Console output formatting | 14.0+   |
| `tqdm`        | Progress bars             | 4.67+   |
| `structlog`   | Structured logging        | 25.0+   |
| `pytest`      | Testing framework         | 8.0+    |
| `docker`      | Containerization          | 27.0+   |

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
│   ├── prompts.py          # LLM prompts
│   ├── search.py           # Hybrid search (NEW)
│   ├── definitions.py      # Definitions auto-linking (NEW)
│   └── logging_util.py     # Query logging (NEW)
├── data/
│   ├── raw/
│   │   ├── cme/            # CME source documents
│   │   │   ├── Fees/       # Subdirectory support (NEW)
│   │   │   └── Agreements/
│   │   ├── opra/           # OPRA source documents (future)
│   │   └── cta_utp/        # CTA/UTP source documents (future)
│   ├── text/
│   │   ├── cme/            # Extracted text files
│   │   ├── opra/
│   │   └── cta_utp/
│   └── chunks/
│       └── {provider}/     # Optional: serialized chunks for debugging
├── index/
│   ├── chroma/             # ChromaDB persistent storage
│   └── bm25/               # BM25 index storage (NEW)
├── logs/
│   └── queries.jsonl       # Query audit log (NEW)
├── api/
│   ├── __init__.py
│   ├── main.py             # FastAPI application (NEW)
│   └── routes.py           # API endpoints (NEW)
├── docker/
│   ├── Dockerfile          # Container definition (NEW)
│   └── docker-compose.yml  # Local multi-service setup (NEW)
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD pipeline (NEW)
├── docs/
│   ├── specs.v0.1.md
│   ├── specs.v0.2.md
│   ├── specs.v0.3.md       # This document
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

### Subdirectory Support (NEW)

Documents can be organized in subdirectories for better management:

```
data/raw/cme/
├── Fees/
│   ├── january-2025-market-data-fee-list.pdf
│   └── schedule-2-rates.pdf
└── Agreements/
    ├── information-license-agreement.pdf
    └── subscriber-terms.pdf
```

- **Recursive discovery**: System scans all subdirectories
- **Path encoding**: Artifacts use path encoding (e.g., `Fees__schedule.pdf.txt`)
- **Deterministic ordering**: Files sorted by relative path for consistency
- **Collision prevention**: Same filename in different subdirectories handled correctly

### Extraction Output

For each source document, produce:

1. **Clean text file** — `data/text/{provider}/{path-encoded-name}.txt`
1. **Metadata JSON** — `data/text/{provider}/{path-encoded-name}.meta.json`

Metadata JSON schema:

```json
{
  "source_file": "information-license-agreement-ila-guide.pdf",
  "provider": "cme",
  "relative_path": "Agreements/ila-guide.pdf",
  "extracted_at": "2026-01-27T10:30:00Z",
  "page_count": 42,
  "extraction_method": "pymupdf",
  "word_count": 15234
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
| Max chunk   | 6000 chars    | Embedding model limit         |

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
    "chunk_id": str,           # Unique: "{provider}_{relative_path}_{index}"
    "provider": str,           # "cme", "opra", "cta_utp"
    "document_name": str,      # Source filename
    "relative_path": str,      # Subdirectory path (e.g., "Fees/schedule.pdf")
    "document_version": str,   # If detectable (e.g., "v5.0")
    "section_heading": str,    # Detected section title or "N/A"
    "page_start": int,         # Starting page number (1-indexed)
    "page_end": int,           # Ending page number
    "chunk_index": int,        # Position within document
    "word_count": int,         # Actual word count
    "is_definitions": bool,    # True if definitions section (NEW)
}
```

### Definitions Handling (NEW)

- Chunks containing "Definitions" or "Defined Terms" in heading get tagged: `"is_definitions": true`
- Definitions chunks are indexed separately for auto-linking
- When query response contains quoted terms, definitions are automatically retrieved and included

______________________________________________________________________

## 8. Vector Database & Search Index

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

### BM25 Index (NEW)

```python
from rank_bm25 import BM25Okapi
import pickle

# Build BM25 index per provider
tokenized_corpus = [chunk["text"].split() for chunk in chunks]
bm25_index = BM25Okapi(tokenized_corpus)

# Save to disk
with open(f"index/bm25/{provider}_index.pkl", "wb") as f:
    pickle.dump(bm25_index, f)
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

## 9. Query Pipeline (Enhanced)

### Query Flow

1. Parse user question
1. Optionally filter by provider(s)
1. **Embed question** using same embedding model
1. **Vector search**: Retrieve top-k chunks from ChromaDB
1. **BM25 search**: Retrieve top-k chunks using keyword matching (NEW)
1. **Hybrid ranking**: Combine results using Reciprocal Rank Fusion (RRF) (NEW)
1. **Definitions auto-linking**: If response contains defined terms, retrieve definitions (NEW)
1. Construct prompt with retrieved context + definitions
1. Generate answer via LLM
1. Format response with citations
1. **Log query** to `logs/queries.jsonl` (NEW)

### Retrieval Parameters

| Parameter           | Default | Notes                                      |
| ------------------- | ------- | ------------------------------------------ |
| top_k (vector)      | 10      | Number of chunks from vector search        |
| top_k (BM25)        | 10      | Number of chunks from keyword search (NEW) |
| final_top_n         | 5       | After hybrid ranking (NEW)                 |
| provider_filter     | None    | Optional: limit to specific provider(s)    |
| include_definitions | True    | Auto-link definitions (NEW)                |

### Hybrid Search Algorithm (NEW)

**Reciprocal Rank Fusion (RRF)**:

```python
def rrf_score(rank: int, k: int = 60) -> float:
    """Compute RRF score for a given rank."""
    return 1.0 / (k + rank)

# Combine vector and BM25 results
for doc in vector_results:
    final_scores[doc.id] += rrf_score(doc.rank)

for doc in bm25_results:
    final_scores[doc.id] += rrf_score(doc.rank)

# Sort by combined score, take top N
top_chunks = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:final_top_n]
```

### Definitions Auto-Linking (NEW)

```python
def extract_quoted_terms(text: str) -> list[str]:
    """Extract terms in quotes from text."""
    return re.findall(r'"([^"]+)"', text)

def retrieve_definitions(terms: list[str], provider: str) -> list[Chunk]:
    """Retrieve definition chunks for given terms."""
    # Query chunks with is_definitions=true
    # Filter by term presence in text
    return definition_chunks
```

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

The system supports two output formats based on the execution context:

### 10.1 Console Output (using Rich)

For CLI execution, output is formatted using the `rich` library for enhanced readability:

```python
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()

# Answer section
console.print(Panel(answer_text, title="Answer", border_style="blue"))

# Supporting clauses
console.print("\n[bold]Supporting Clauses[/bold]\n")
for clause in clauses:
    console.print(f'> "{clause.text}"')
    console.print(f'> — [dim]{clause.document}, {clause.section}[/dim]\n')

# Definitions (if applicable)
if definitions:
    console.print("\n[bold]Definitions[/bold]\n")
    for term, definition in definitions.items():
        console.print(f'> [bold]{term}[/bold]: {definition.text}')
        console.print(f'> — [dim]{definition.document}, {definition.section}[/dim]\n')

# Citations
console.print("\n[bold]Citations[/bold]\n")
for citation in citations:
    console.print(f'- [bold]{citation.document}[/bold] (Page {citation.page}): {citation.section}')

# Notes (if applicable)
if notes:
    console.print(f'\n[italic]{notes}[/italic]')
```

### 10.2 JSON Output

For programmatic access or web UI integration, output is structured as JSON:

```json
{
  "answer": "Clear, concise answer grounded in documents",
  "supporting_clauses": [
    {
      "text": "Quoted excerpt from document",
      "document": "Document Name",
      "section": "Section heading",
      "page_start": 12,
      "page_end": 13
    }
  ],
  "definitions": [
    {
      "term": "Subscriber",
      "definition": "Definition text",
      "document": "Document Name",
      "section": "Section heading",
      "page": 5
    }
  ],
  "citations": [
    {
      "provider": "cme",
      "document": "Document Name",
      "relative_path": "Fees/schedule.pdf",
      "section": "Section heading",
      "page": 12
    }
  ],
  "notes": "Any ambiguities or cross-references",
  "metadata": {
    "query_id": "uuid-string",
    "providers": ["cme"],
    "chunks_retrieved": 5,
    "response_time_ms": 2847,
    "llm_provider": "anthropic"
  }
}
```

### Citation Format

Each citation must include:

- Provider name (if multi-provider query)
- Document filename (or relative path if in subdirectory)
- Section heading or identifier
- Page number(s)

______________________________________________________________________

## 11. Query Logging (NEW)

All queries are logged to `logs/queries.jsonl` for audit and analysis.

### Log Entry Schema

```json
{
  "timestamp": "2026-01-27T14:30:00Z",
  "query_id": "uuid-string",
  "question": "What are the redistribution requirements?",
  "providers": ["cme"],
  "vector_chunks": ["cme_Fees__schedule_12", "cme_Agreements__ila_5"],
  "bm25_chunks": ["cme_Agreements__ila_5", "cme_Fees__rates_3"],
  "final_chunks": ["cme_Agreements__ila_5", "cme_Fees__schedule_12"],
  "definitions_linked": ["Subscriber", "Redistribution"],
  "answer_length": 342,
  "response_time_ms": 2847,
  "llm_provider": "anthropic",
  "error": null
}
```

### Privacy & Compliance

- Logs stored locally (not transmitted)
- No PII captured (only query text and system metadata)
- Logs rotated monthly
- Can be disabled via config flag

______________________________________________________________________

## 12. REST API Specification (NEW)

### Technology

- **Framework**: FastAPI
- **Server**: Uvicorn (ASGI)
- **Port**: 8000 (default)
- **Documentation**: Auto-generated OpenAPI (Swagger UI)

### Endpoints

#### 12.1 Query Endpoint

**POST** `/api/v1/query`

Execute a query against the document collection.

**Request Body**:

```json
{
  "question": "What are the redistribution requirements for CME data?",
  "providers": ["cme"],
  "search_mode": "hybrid",
  "top_k": 10,
  "include_definitions": true
}
```

**Response** (200 OK):

```json
{
  "query_id": "uuid-string",
  "answer": "Redistribution requires written consent from CME...",
  "supporting_clauses": [...],
  "definitions": [...],
  "citations": [...],
  "notes": null,
  "metadata": {
    "providers": ["cme"],
    "chunks_retrieved": 5,
    "response_time_ms": 2847,
    "llm_provider": "anthropic"
  }
}
```

#### 12.2 Document Listing Endpoint

**GET** `/api/v1/documents?provider={provider}`

List all indexed documents for a provider.

**Response** (200 OK):

```json
{
  "provider": "cme",
  "documents": [
    {
      "filename": "information-license-agreement-ila-guide.pdf",
      "relative_path": "Agreements/ila-guide.pdf",
      "page_count": 42,
      "word_count": 15234,
      "chunk_count": 28,
      "extracted_at": "2026-01-27T10:30:00Z"
    }
  ]
}
```

#### 12.3 Ingestion Trigger Endpoint

**POST** `/api/v1/ingest/{provider}`

Trigger re-ingestion for a specific provider.

**Response** (202 Accepted):

```json
{
  "job_id": "uuid-string",
  "provider": "cme",
  "status": "started",
  "message": "Ingestion job queued"
}
```

#### 12.4 System Stats Endpoint

**GET** `/api/v1/stats`

Retrieve system statistics.

**Response** (200 OK):

```json
{
  "providers": [
    {
      "name": "cme",
      "document_count": 35,
      "chunk_count": 847,
      "index_size_mb": 142
    }
  ],
  "total_queries": 1523,
  "index_updated_at": "2026-01-27T08:00:00Z"
}
```

#### 12.5 Query Logs Endpoint

**GET** `/api/v1/logs?limit={limit}&offset={offset}`

Retrieve recent query logs (paginated).

**Response** (200 OK):

```json
{
  "logs": [
    {
      "timestamp": "2026-01-27T14:30:00Z",
      "query_id": "uuid-string",
      "question": "What are the redistribution requirements?",
      "providers": ["cme"],
      "response_time_ms": 2847,
      "error": null
    }
  ],
  "total": 1523,
  "limit": 10,
  "offset": 0
}
```

#### 12.6 Health Check Endpoint

**GET** `/health`

Health check for load balancer.

**Response** (200 OK):

```json
{
  "status": "healthy",
  "timestamp": "2026-01-27T14:30:00Z",
  "version": "0.3"
}
```

### Authentication

- **Method**: API Key (Header: `X-API-Key`)
- **Optional**: For local development, authentication can be disabled
- **Production**: Required for AWS deployment

### Rate Limiting

- **Default**: 60 requests per minute per API key
- **Configurable**: Via environment variable `RATE_LIMIT_RPM`

### CORS

- **Enabled**: For web client integration
- **Configurable**: Allowed origins via environment variable

______________________________________________________________________

## 13. Deployment Specification (NEW)

### 13.1 Docker Containerization

**Dockerfile**:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install uv && uv sync

# Copy application code
COPY . .

# Expose ports
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "api.main:app", "--host=0.0.0.0", "--port=8000"]
```

**docker-compose.yml** (local development):

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./index:/app/index
      - ./logs:/app/logs
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - LLM_PROVIDER=anthropic
```

### 13.2 AWS ECS/Fargate Deployment

**Architecture**:

```
┌──────────────────────────────────────────────────────────┐
│                      Internet Gateway                     │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│              Application Load Balancer (ALB)              │
│              (HTTPS termination, health checks)           │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                    ECS Fargate Cluster                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Task: licencing-rag-app                            │ │
│  │  - CPU: 2 vCPU                                      │ │
│  │  - Memory: 4 GB                                     │ │
│  │  - Port: 8000                                       │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                      EFS Volume                           │
│  /data, /index, /logs (persistent storage)                │
└───────────────────────────────────────────────────────────┘
```

**Resource Requirements**:

| Resource | Specification  | Notes                       |
| -------- | -------------- | --------------------------- |
| CPU      | 2 vCPU         | Sufficient for FastAPI      |
| Memory   | 4 GB           | ChromaDB + embeddings cache |
| Storage  | 20 GB EFS      | Documents + indexes         |
| Network  | Private subnet | ALB for public access       |

**Environment Variables**:

```bash
ANTHROPIC_API_KEY=<secret-from-secrets-manager>
LLM_PROVIDER=anthropic
CHROMA_DIR=/mnt/efs/index/chroma
RAW_DATA_DIR=/mnt/efs/data/raw
```

### 13.3 CI/CD Pipeline

**GitHub Actions Workflow** (`.github/workflows/deploy.yml`):

```yaml
name: Deploy to AWS ECS

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install uv
          uv sync
          pytest

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v2
      
      - name: Build and push Docker image
        run: |
          docker build -t licencing-rag .
          docker tag licencing-rag:latest $ECR_REGISTRY/licencing-rag:latest
          docker push $ECR_REGISTRY/licencing-rag:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster licencing-rag-cluster \
            --service licencing-rag-service \
            --force-new-deployment
```

______________________________________________________________________

## 14. CLI Interface

The CLI is available as a package entry point for convenient access:

### Installation

```bash
# Install in development mode (from project root)
pip install -e .

# After installation, use the 'rag' command globally
rag --help
```

Alternatively, use Python module syntax without installation:

```bash
python -m rag --help
```

### Commands

```bash
# Ingest documents for a provider
rag ingest --provider cme

# Ingest all providers
rag ingest --all

# Query with default settings (hybrid search)
rag query "What are the redistribution requirements?"

# Query specific provider
rag query --provider cme "What fees apply to derived data?"

# Query with search mode override
rag query --mode vector "Definition of subscriber"

# Query with output format
rag query --format json "Definition of subscriber" > result.json
rag query --format console "What are the fees?"  # default (using rich)

# Query multiple providers
rag query --provider cme --provider opra "Definition of subscriber"

# List indexed documents
rag list --provider cme

# List all providers
rag list

# View query logs
rag logs --tail 10
rag logs --provider cme --since "2026-01-27"

# Start REST API server
rag serve --port 8000 --host 0.0.0.0

# Health check
rag health
```

### Configuration

Using `pyproject.toml` entry point:

```toml
[project.scripts]
rag = "app.cli:main"
```

### Exit Codes

| Code | Meaning              |
| ---- | -------------------- |
| 0    | Success              |
| 1    | General error        |
| 2    | No documents found   |
| 3    | Provider not indexed |
| 4    | Search index error   |

______________________________________________________________________

## 15. Security & Privacy

- Fully local execution (except Claude API calls)
- No telemetry
- Query logging configurable and local-only
- Vector DB stored locally with filesystem permissions
- API keys stored in environment variables (never committed)
- Docker secrets for cloud deployment
- HTTPS termination at ALB
- Private VPC subnets for ECS tasks

______________________________________________________________________

## 16. Success Criteria

The system is successful if:

| Criterion       | Measurement                                   |
| --------------- | --------------------------------------------- |
| Grounding       | Never answers beyond provided documents       |
| Citations       | Every answer includes document + section      |
| Refusal         | Correctly refuses when info not found         |
| Retrieval       | Hybrid search outperforms vector-only by >15% |
| Definitions     | Auto-links >90% of quoted terms correctly     |
| Maintainability | Adding documents requires re-ingestion only   |
| Performance     | \<10s response time on standard laptop        |
| UI Usability    | Non-technical users complete queries in \<30s |
| Deployment      | Zero-downtime updates via ECS rolling deploy  |
| Extensibility   | New provider added without code changes       |

______________________________________________________________________

## 17. Performance & Scalability Targets

### Local Execution

| Metric               | Target     | Notes                        |
| -------------------- | ---------- | ---------------------------- |
| Query response time  | \<10s      | Includes hybrid search + LLM |
| Ingestion throughput | 5 docs/min | PDF extraction + chunking    |
| Index size           | \<2 GB     | For 100 documents            |
| Memory usage         | \<4 GB     | ChromaDB + embeddings cache  |

### Cloud Deployment

| Metric              | Target | Notes                          |
| ------------------- | ------ | ------------------------------ |
| Concurrent users    | 10-20  | Single Fargate task            |
| Query response time | \<5s   | Claude API faster than Ollama  |
| Uptime              | 99.5%  | ALB health checks + auto-scale |
| Cold start          | \<30s  | ECS task launch time           |

______________________________________________________________________

## 18. Future Enhancements (Deferred to v0.4+)

| Enhancement                  | Priority | Notes                       |
| ---------------------------- | -------- | --------------------------- |
| OpenAI API support           | Medium   | Alternative to Claude       |
| CTA/UTP document ingestion   | Medium   | After OPRA                  |
| Clause comparison            | Low      | Cross-document analysis     |
| Risk flag extraction         | Low      | Audit, termination triggers |
| Version diffing              | Low      | Compare document versions   |
| Multi-language support       | Low      | Non-English documents       |
| Advanced analytics dashboard | Low      | Query patterns, trends      |

______________________________________________________________________

## 19. Guiding Principles

1. **Correctness over fluency** — Precise, grounded answers beat eloquent speculation
1. **Traceability** — Every statement must cite its source
1. **Refusal is a feature** — Saying "not found" is a correct answer
1. **Simplicity** — Minimal dependencies, clear code, no magic
1. **Extensibility** — Adding providers should be configuration, not code surgery
1. **Performance** — Fast enough to be useful, not overengineered
1. **Privacy** — Local-first, optional cloud deployment with explicit user control
1. **Auditability** — All queries logged for compliance and analysis
