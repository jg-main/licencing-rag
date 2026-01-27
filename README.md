# License Intelligence System - Local RAG

**Version:** 0.3\
**Status:** Sprint 1-2 Complete, Sprint 3-5 In Development

A local, private legal Q&A system that answers questions **exclusively** based on curated license agreements and exhibits from multiple market data providers. No training. No cloud (optional). No hallucinations (by design).

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Document Management](#document-management)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Development](#development)
- [Deployment](#deployment-not-implemented-yet)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)

______________________________________________________________________

## Overview

This is **not** a general chatbot and **not** a trained LLM. It is a **retrieval-grounded legal analysis tool** that:

- ✅ Responds **only** using the provided documents
- ✅ Explicitly refuses to answer when the documents are silent
- ✅ Always provides **citations** (provider, document name, section, page)
- ✅ Supports multiple data providers
- ✅ Uses Claude API for answer generation (with Ollama fallback)
- ✅ Uses local embeddings via Ollama (nomic-embed-text)
- ⏳ Supports hybrid search (vector + keyword) - **NOT IMPLEMENTED YET**
- ⏳ Auto-links defined terms to definitions - **NOT IMPLEMENTED YET**
- ⏳ Logs all queries for audit - **NOT IMPLEMENTED YET**
- ⏳ Provides REST API for programmatic access - **NOT IMPLEMENTED YET**
- ⏳ Deployable to AWS ECS/Fargate - **NOT IMPLEMENTED YET**

### Supported Data Providers

| Provider  | Status     | Document Count | Priority |
| --------- | ---------- | -------------- | -------- |
| CME Group | ✅ Active  | ~35 documents  | P0       |
| OPRA      | ⏳ Planned | TBD            | P1       |
| CTA/UTP   | ⏳ Planned | TBD            | P2       |

### Supported LLM Providers

| Provider | Status     | Use Case                     |
| -------- | ---------- | ---------------------------- |
| Claude   | ✅ Active  | Primary (fast, high-quality) |
| Ollama   | ✅ Active  | Fallback (local, private)    |
| OpenAI   | ⏳ Planned | Alternative                  |

______________________________________________________________________

## Features

### ✅ Sprint 1-2: MVP & Robustness (IMPLEMENTED)

#### Core Functionality

- ✅ **PDF & DOCX Extraction** - Extract text with page tracking from PDF and DOCX files
- ✅ **Smart Chunking** - Section-aware chunking with 500-800 word targets and metadata
- ✅ **Vector Search** - ChromaDB with Ollama embeddings (nomic-embed-text)
- ✅ **Multi-Provider Support** - Organize documents by data provider (CME, OPRA, etc.)
- ✅ **Subdirectory Organization** - Nested folder structure (e.g., `CME/Fees/`, `CME/Agreements/`)
- ✅ **Page-Level Citations** - Every answer includes exact document references
- ✅ **Grounded Responses** - Explicit refusal when answer not in documents
- ✅ **Dual LLM Support** - Claude API (primary) or Ollama (fallback)

#### Quality & Testing

- ✅ **Error Handling** - Robust handling of corrupted PDFs, connection issues
- ✅ **Comprehensive Testing** - 75 tests covering core functionality
- ✅ **Structured Logging** - Using structlog for detailed diagnostics
- ✅ **Quality Validation** - Extraction quality checks

#### CLI Interface

- ✅ `rag ingest --provider <name>` - Ingest documents
- ✅ `rag query "<question>"` - Query the knowledge base
- ✅ `rag list --provider <name>` - List indexed documents
- ⏳ `rag logs --tail N` - View query logs - **NOT IMPLEMENTED YET**
- ⏳ `rag serve --port 8000` - Start REST API server - **NOT IMPLEMENTED YET**

### ⏳ Sprint 3: Enhanced Search & Logging (NOT IMPLEMENTED YET)

#### Hybrid Search

- ⏳ **BM25 Keyword Search** - Complement vector search with keyword matching
- ⏳ **Reciprocal Rank Fusion (RRF)** - Combine vector + keyword results for better retrieval
- ⏳ **Search Mode Selection** - Choose vector-only, keyword-only, or hybrid
- ⏳ **Performance Benchmarking** - Target: >15% improvement over vector-only

#### Definitions Auto-Linking

- ⏳ **Quoted Term Extraction** - Detect defined terms in answers (e.g., "Subscriber")
- ⏳ **Definitions Index** - Build index of definition chunks (is_definitions=true)
- ⏳ **Automatic Retrieval** - Auto-fetch and include relevant definitions
- ⏳ **Definition Caching** - Reduce redundant retrievals

#### Query Logging

- ⏳ **JSONL Audit Logs** - Log all queries to `logs/queries.jsonl`
- ⏳ **Privacy Controls** - Disable logging flag, no PII beyond query text
- ⏳ **Log Rotation** - Monthly rotation
- ⏳ **Query Analysis** - CLI command to view and analyze logs

#### Output Formats

- ⏳ **Rich Console Output** - Formatted CLI output with panels, colors, markdown
- ⏳ **JSON Output** - Structured JSON for programmatic access
- ⏳ **Format Selection** - `--format` flag (console/json)

### ⏳ Sprint 4: REST API (NOT IMPLEMENTED YET)

#### FastAPI Service

- ⏳ **POST /api/v1/query** - Execute queries programmatically
- ⏳ **GET /api/v1/documents** - List indexed documents with filtering
- ⏳ **GET /api/v1/stats** - System statistics (doc count, chunk count, index size)
- ⏳ **POST /api/v1/ingest/{provider}** - Trigger re-ingestion (async job)
- ⏳ **GET /api/v1/logs** - Query logs with pagination
- ⏳ **GET /health** - Health check endpoint

#### API Features

- ⏳ **OpenAPI Documentation** - Auto-generated Swagger UI
- ⏳ **API Key Authentication** - X-API-Key header
- ⏳ **Rate Limiting** - 60 req/min default, configurable
- ⏳ **CORS Support** - Configurable allowed origins
- ⏳ **Error Handling** - Consistent error response format
- ⏳ **Request/Response Logging** - Detailed API access logs

### ⏳ Sprint 5: AWS Deployment (NOT IMPLEMENTED YET)

#### Docker Containerization

- ⏳ **Multi-stage Dockerfile** - Optimized build (\<1GB image)
- ⏳ **docker-compose.yml** - Local multi-service development
- ⏳ **Volume Mounts** - Persistent storage for data, index, logs
- ⏳ **Environment Configuration** - Secrets management

#### AWS Infrastructure

- ⏳ **ECS/Fargate Cluster** - Serverless container orchestration
- ⏳ **Application Load Balancer** - HTTPS termination with ACM certificate
- ⏳ **EFS File System** - Persistent storage for documents and index
- ⏳ **ECR Repository** - Private Docker image registry
- ⏳ **VPC Configuration** - Public/private subnets, security groups

#### CI/CD Pipeline

- ⏳ **GitHub Actions Workflow** - Automated deployment pipeline
- ⏳ **Test Stage** - Run pytest suite
- ⏳ **Build Stage** - Docker image build
- ⏳ **Push Stage** - Upload to ECR
- ⏳ **Deploy Stage** - ECS service update (blue/green)
- ⏳ **Rollback Procedure** - Automated rollback on failure

#### Monitoring & Operations

- ⏳ **CloudWatch Dashboard** - System metrics visualization
- ⏳ **Log Aggregation** - Centralized logging
- ⏳ **Alerting Rules** - CPU, memory, error rate alarms
- ⏳ **Auto-scaling** - Min 1, max 3 tasks based on CPU/memory
- ⏳ **Cost Monitoring** - Estimated ~$62/month
- ⏳ **Backup/Restore** - Disaster recovery procedures

______________________________________________________________________

## Quick Start

### Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** - Fast Python package manager
- **[Ollama](https://ollama.com/)** - For local embeddings (required) and optional LLM fallback
- **Anthropic API Key** - For Claude API (recommended for production)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd licencing-rag

# Install dependencies with uv
uv sync

# Install CLI entry point (enables 'rag' command) - NOT IMPLEMENTED YET
pip install -e .

# Pull embedding model (REQUIRED - used even with Claude API)
ollama pull nomic-embed-text
```

> **⚠️ CLI Note:** The `rag` command shown throughout this README is the planned interface from specs.v0.3.md.\
> **Current implementation:** Use `python main.py` instead of `rag` until Sprint 1 CLI entry point is completed.\
> Example: `python main.py query "Your question"` instead of `rag query "Your question"`

### Choose Your LLM Provider

#### Option A: Claude API (Recommended) - Fast, High Quality

```bash
# Get API key from https://console.anthropic.com/
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"

# Run queries (uses Claude for answers, Ollama for embeddings)
rag query "What are the CME fees?"
```

**Cost:** ~$0.003 per query (~$9/month for 100 queries/day)

#### Option B: Ollama (Free, Local) - Requires RAM

```bash
# Pull LLM model
ollama pull llama3.2:3b   # For limited RAM (<8GB)
ollama pull llama3.1:8b   # For 8GB+ RAM (better quality)

# Run queries (default provider)
export LLM_PROVIDER="ollama"  # optional, this is the default
rag query "What are the CME fees?"
```

**Cost:** Free, but slower and requires local compute

### Basic Workflow

```bash
# 1. Ingest documents
rag ingest --provider cme

# 2. Query the knowledge base
rag query "What is a subscriber?"

# 3. List indexed documents
rag list --provider cme
```

______________________________________________________________________

## Usage

### CLI Commands

#### Ingestion

```bash
# Ingest all documents for a provider
rag ingest --provider cme

# Ingest specific provider (future)
rag ingest --provider opra
```

**What it does:**

- Recursively scans `data/raw/{provider}/` for PDF and DOCX files
- Extracts text with page tracking
- Chunks documents with section detection
- Generates embeddings via Ollama
- Stores in ChromaDB collection

#### Querying

```bash
# Basic query
rag query "What are the redistribution requirements?"

# Query specific provider (NOT IMPLEMENTED YET)
rag query --provider cme "What are the fees?"

# Query all providers (NOT IMPLEMENTED YET)
rag query --provider all "What is a subscriber?"

# JSON output (NOT IMPLEMENTED YET)
rag query --format json "What are the fees?" > result.json

# Console output with Rich formatting (NOT IMPLEMENTED YET)
rag query --format console "What are the fees?"
```

**What it does:**

- Embeds question using Ollama
- Retrieves top-K relevant chunks from ChromaDB
- ⏳ (Sprint 3) Performs hybrid search (vector + BM25)
- ⏳ (Sprint 3) Auto-links definitions
- Generates answer via LLM (Claude or Ollama)
- ⏳ (Sprint 3) Logs query to `logs/queries.jsonl`
- Returns answer with citations

#### Document Management

```bash
# List all documents for a provider
rag list --provider cme

# Show document details (NOT IMPLEMENTED YET)
rag list --provider cme --detailed

# Show statistics (NOT IMPLEMENTED YET)
rag stats
```

#### Query Logs (NOT IMPLEMENTED YET - Sprint 3)

```bash
# View recent queries
rag logs --tail 10

# Filter by provider
rag logs --provider cme --tail 20

# Export logs
rag logs --export logs_export.jsonl
```

#### REST API Server (NOT IMPLEMENTED YET - Sprint 4)

```bash
# Start API server
rag serve --port 8000 --host 0.0.0.0

# With API key authentication
rag serve --api-key your-secret-key

# Development mode (auto-reload)
rag serve --reload
```

### REST API (NOT IMPLEMENTED YET - Sprint 4)

#### Query Endpoint

**POST** `/api/v1/query`

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "question": "What are the redistribution requirements for CME data?",
    "providers": ["cme"],
    "search_mode": "hybrid",
    "top_k": 5,
    "include_definitions": true
  }'
```

**Response:**

```json
{
  "query_id": "uuid-string",
  "answer": "Clear, concise answer grounded in documents",
  "supporting_clauses": [
    {
      "text": "Exact clause text from document",
      "document": "information-license-agreement-ila-guide.pdf",
      "section": "Section 5: Redistribution",
      "page": 12,
      "provider": "cme"
    }
  ],
  "definitions": [
    {
      "term": "Subscriber",
      "definition": "Definition text from document",
      "source": "cme/Agreements/subscriber-terms.pdf",
      "page": 3
    }
  ],
  "citations": [
    {
      "document": "information-license-agreement-ila-guide.pdf",
      "section": "Section 5: Redistribution",
      "pages": [12, 13],
      "provider": "cme"
    }
  ],
  "metadata": {
    "providers_searched": ["cme"],
    "chunks_retrieved": 5,
    "search_mode": "hybrid",
    "response_time_ms": 1420
  }
}
```

#### Other Endpoints

```bash
# List documents
GET /api/v1/documents?provider=cme

# System statistics
GET /api/v1/stats

# Trigger ingestion
POST /api/v1/ingest/cme

# Query logs
GET /api/v1/logs?limit=100&offset=0

# Health check
GET /health
```

______________________________________________________________________

## Document Management

### Directory Structure

```
data/
├── raw/                    # Source documents
│   ├── cme/                # CME Group documents
│   │   ├── Fees/           # Subdirectory for fee schedules
│   │   │   ├── january-2025-market-data-fee-list.pdf
│   │   │   └── schedule-2-rates.pdf
│   │   └── Agreements/     # Subdirectory for license agreements
│   │       ├── information-license-agreement-ila-guide.pdf
│   │       └── subscriber-terms.pdf
│   ├── opra/               # OPRA documents (future)
│   └── cta_utp/            # CTA/UTP documents (future)
├── text/                   # Extracted text files
│   └── cme/
│       ├── Fees__january-2025-market-data-fee-list.pdf.txt
│       ├── Fees__january-2025-market-data-fee-list.pdf.meta.json
│       ├── Agreements__information-license-agreement-ila-guide.pdf.txt
│       └── Agreements__information-license-agreement-ila-guide.pdf.meta.json
└── chunks/                 # Serialized chunks (optional, for debugging)
    └── cme/

index/
├── chroma/                 # ChromaDB vector database
│   └── cme_docs/           # Collection per provider
└── bm25/                   # BM25 keyword index (NOT IMPLEMENTED YET)
    └── cme_index.pkl

logs/
└── queries.jsonl           # Query audit log (NOT IMPLEMENTED YET)
```

### Subdirectory Support

✅ **IMPLEMENTED** - Documents can be organized in nested subdirectories:

- Recursive discovery of all PDF/DOCX files
- Path encoding in artifacts (e.g., `Fees__schedule.pdf.txt`)
- Deterministic ordering by relative path
- Collision prevention for duplicate filenames

**Example:**

```bash
# Place documents in subdirectories
mkdir -p data/raw/cme/Fees
mkdir -p data/raw/cme/Agreements
cp fee-schedule.pdf data/raw/cme/Fees/
cp license-agreement.pdf data/raw/cme/Agreements/

# Ingest recursively discovers all documents
rag ingest --provider cme
```

### Supported Formats

| Format | Extractor   | Notes                          | Status         |
| ------ | ----------- | ------------------------------ | -------------- |
| PDF    | PyMuPDF     | Native text extraction, no OCR | ✅ Implemented |
| DOCX   | python-docx | Paragraph-based extraction     | ✅ Implemented |

**Note:** OCR for scanned PDFs is out of scope. Assume text-based PDFs.

______________________________________________________________________

## Configuration

### Environment Variables

| Variable            | Default        | Description                                         | Required        |
| ------------------- | -------------- | --------------------------------------------------- | --------------- |
| `LLM_PROVIDER`      | `ollama`       | LLM provider: `ollama` or `anthropic`               | No              |
| `ANTHROPIC_API_KEY` | -              | Claude API key                                      | If using Claude |
| `RATE_LIMIT_RPM`    | `60`           | API rate limit (requests/min) - NOT IMPLEMENTED YET | No              |
| `CHROMA_DIR`        | `index/chroma` | ChromaDB storage directory                          | No              |

### Configuration File

Edit `app/config.py` for advanced settings:

```python
# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = "llama3.2:3b"  # Ollama model
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"  # Claude model

# Embedding Configuration
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768

# Chunking Parameters
CHUNK_SIZE = 500  # words
CHUNK_OVERLAP = 100  # words
MIN_CHUNK_SIZE = 100  # words
MAX_CHUNK_CHARS = 6000  # characters

# Retrieval Parameters (NOT IMPLEMENTED YET - Sprint 3)
TOP_K_VECTOR = 10  # Vector search results
TOP_K_BM25 = 10    # BM25 search results
FINAL_TOP_N = 5    # Final chunks after hybrid ranking

# Search Configuration (NOT IMPLEMENTED YET - Sprint 3)
DEFAULT_SEARCH_MODE = "hybrid"  # vector, keyword, hybrid

# Logging (NOT IMPLEMENTED YET - Sprint 3)
QUERY_LOGGING_ENABLED = True
LOG_ROTATION = "monthly"
```

______________________________________________________________________

## Architecture

### System Flow

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
│                 (keyword index per provider) [Sprint 3]          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Query Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  User Question  →  Embed  →  Vector Search (Top-K)              │
│                      ↓                                           │
│                  BM25 Search (Top-K) [Sprint 3]                  │
│                      ↓                                           │
│              Hybrid Ranking (RRF) [Sprint 3]  →  Top-N Chunks    │
│                      ↓                                           │
│         Definitions Auto-Linking [Sprint 3] (if needed)          │
│                      ↓                                           │
│              LLM Prompt (context + question)                     │
│                      ↓                                           │
│              Answer + Citations                                  │
│                      ↓                                           │
│              Query Logging [Sprint 3] (logs/queries.jsonl)       │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component        | Technology                | Purpose                           | Status      |
| ---------------- | ------------------------- | --------------------------------- | ----------- |
| Runtime          | Python 3.13+              | Application runtime               | ✅ Active   |
| LLM (Primary)    | Claude Sonnet 4.5         | Answer generation (Anthropic API) | ✅ Active   |
| LLM (Fallback)   | Llama 3.1/3.2 (Ollama)    | Local answer generation           | ✅ Active   |
| Embeddings       | nomic-embed-text (Ollama) | 768-dim vectors                   | ✅ Active   |
| Vector DB        | ChromaDB 1.4+             | Vector storage & search           | ✅ Active   |
| Keyword Search   | rank-bm25 0.2+            | BM25 keyword search               | ⏳ Sprint 3 |
| PDF Extraction   | PyMuPDF 1.26+             | PDF text extraction               | ✅ Active   |
| DOCX Extraction  | python-docx 1.2+          | DOCX text extraction              | ✅ Active   |
| REST API         | FastAPI 0.115+            | HTTP API framework                | ⏳ Sprint 4 |
| ASGI Server      | Uvicorn 0.32+             | Production web server             | ⏳ Sprint 4 |
| CLI Formatting   | Rich 14.0+                | Terminal output formatting        | ⏳ Sprint 3 |
| Logging          | structlog 25.0+           | Structured logging                | ✅ Active   |
| Testing          | pytest 8.0+               | Unit and integration tests        | ✅ Active   |
| Containerization | Docker 27.0+              | Application containerization      | ⏳ Sprint 5 |

### Key Design Decisions

1. **One ChromaDB collection per provider** — Enables provider-specific queries and simpler re-ingestion
1. **Hybrid search (Sprint 3)** — Combines semantic (vector) and keyword (BM25) retrieval for better coverage
1. **Definitions auto-linking (Sprint 3)** — Automatically retrieves definition chunks when terms are referenced
1. **Unified query interface** — Can search all providers or filter to specific ones
1. **Metadata-rich chunks** — Every chunk carries full provenance for citation
1. **Subdirectory support** — Organize documents in folders (Fees/, Agreements/, etc.)
1. **Query logging (Sprint 3)** — All queries logged to JSONL for audit and analysis
1. **FastAPI over Streamlit (Sprint 4)** — REST API for programmatic access vs. web UI
1. **AWS ECS/Fargate (Sprint 5)** — Serverless container deployment vs. EC2

______________________________________________________________________

## Development

### Project Setup

```bash
# Clone and install
git clone <repo-url>
cd licencing-rag
uv sync
pip install -e .

# Run quality checks
make qa

# Run tests
make test

# Format code
make format

# Type checking
make typecheck
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_ingest.py

# Run with verbose output
pytest -v
```

**Test Coverage:** 75 tests (64 core + 11 subdirectory)

### Code Quality

```bash
# Format with ruff
ruff format .

# Lint with ruff
ruff check .

# Type check with mypy
mypy app/

# All quality checks
make qa
```

### Adding a New Provider

1. Create directory: `mkdir -p data/raw/{provider}`
1. Add documents to the directory
1. Update `app/config.py`: Add provider to `PROVIDERS` list
1. Ingest: `rag ingest --provider {provider}`
1. Query: `rag query --provider {provider} "Your question"`

______________________________________________________________________

## Deployment (NOT IMPLEMENTED YET - Sprint 5)

### Local Docker

```bash
# Build image
docker build -t rag-system -f docker/Dockerfile .

# Run container
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/index:/app/index \
  -v $(pwd)/logs:/app/logs \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  rag-system

# Use docker-compose
docker-compose -f docker/docker-compose.yml up
```

### AWS ECS/Fargate Deployment

**Architecture:**

```
Internet → Route53 → ALB (HTTPS) → ECS Fargate → EFS (storage)
                                        ↓
                                  CloudWatch Logs
```

**Resources:**

| Resource    | Spec         | Cost (monthly) |
| ----------- | ------------ | -------------- |
| ECS Fargate | 2 vCPU, 4 GB | ~$35           |
| ALB         | 1 instance   | ~$20           |
| EFS         | 20 GB        | ~$6            |
| ECR         | \<1 GB       | ~$1            |
| **Total**   |              | **~$62/month** |

**Deployment Steps:**

1. **Infrastructure Setup**

   - Create VPC with public/private subnets
   - Configure security groups
   - Set up EFS file system
   - Create ECR repository
   - Create ECS cluster (Fargate)
   - Configure Application Load Balancer
   - Set up ACM certificate for HTTPS

1. **CI/CD Pipeline** (GitHub Actions)

   - Push to `main` branch triggers workflow
   - Run test suite (`pytest`)
   - Build Docker image
   - Push to ECR
   - Update ECS service (blue/green deployment)
   - Send notification (Slack/email)

1. **Monitoring**

   - CloudWatch dashboard for metrics
   - Alarms for CPU, memory, error rate
   - Auto-scaling (min: 1, max: 3 tasks)
   - Log aggregation

**Manual Deployment:**

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -t rag-system .
docker tag rag-system:latest <account>.dkr.ecr.us-east-1.amazonaws.com/rag-system:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/rag-system:latest

# Update ECS service
aws ecs update-service --cluster rag-cluster --service rag-service --force-new-deployment
```

______________________________________________________________________

## Troubleshooting

### Common Issues

#### "Cannot connect to Ollama"

**Problem:** Ollama server is not running.

**Solution:**

```bash
# Start Ollama
ollama serve

# Or on macOS, ensure the Ollama app is running
```

#### "Model not found" (Ollama)

**Problem:** The required model hasn't been downloaded.

**Solution:**

```bash
# Pull embedding model (REQUIRED)
ollama pull nomic-embed-text

# Pull LLM model (if using Ollama for answers)
ollama pull llama3.2:3b
ollama pull llama3.1:8b
```

#### "ANTHROPIC_API_KEY environment variable is required"

**Problem:** Claude API key not configured.

**Solution:**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"
```

Get an API key from [https://console.anthropic.com/](https://console.anthropic.com/)

#### "No index found" or "Collection not found"

**Problem:** Documents haven't been ingested yet.

**Solution:**

```bash
rag ingest --provider cme
```

#### "Rate limit exceeded" (Claude API)

**Problem:** Too many requests to Claude API.

**Solution:**

- Wait 60 seconds and try again
- Upgrade API plan at [https://console.anthropic.com/](https://console.anthropic.com/)
- Switch to Ollama: `export LLM_PROVIDER="ollama"`

#### Empty or poor extraction results

**Problem:** PDF may be scanned images without text layer.

**Solution:**

```bash
# Enable debug logging to see extraction details
rag --debug ingest --provider cme

# Check extracted text manually
cat data/text/cme/your-document.pdf.txt
```

**Note:** OCR is out of scope. Use text-based PDFs.

#### Slow query performance

**Problem:** Large document set or underpowered hardware.

**Solutions:**

- Use Claude API instead of Ollama for faster LLM response
- Reduce `TOP_K` in config
- Wait for Sprint 3 hybrid search for better precision (fewer chunks needed)
- Upgrade hardware (more RAM for Ollama)

#### ChromaDB version mismatch

**Problem:** Existing index created with older ChromaDB version.

**Solution:**

```bash
# Delete old index
rm -rf index/chroma

# Re-ingest
rag ingest --provider cme
```

### Debug Mode

Enable verbose logging with `--debug`:

```bash
rag --debug ingest --provider cme
rag --debug query "What are the fees?"
```

This will show:

- Extraction progress and chunk counts
- Embedding generation
- ChromaDB operations
- LLM prompt and response
- Error stack traces

### Getting Help

- Check the [RAG Tutorial](docs/rag-tutorial.md) for concepts
- Review [Specs v0.3](docs/specs.v0.3.md) for technical details
- Review [Implementation Plan](docs/implementation-plan.md) for architecture
- Check [Subdirectory Implementation](SUBDIRECTORY_IMPLEMENTATION.md) for subdirectory details

______________________________________________________________________

## Documentation

### Main Documentation

- **[specs.v0.3.md](docs/specs.v0.3.md)** - Complete technical specifications
- **[implementation-plan.md](docs/implementation-plan.md)** - Development roadmap and task breakdown
- **[SUBDIRECTORY_IMPLEMENTATION.md](SUBDIRECTORY_IMPLEMENTATION.md)** - Subdirectory support details

### Additional Resources

- **[RAG Tutorial](docs/rag-tutorial.md)** - Beginner's guide to RAG concepts (if exists)
- **[specs.v0.1.md](docs/specs.v0.1.md)** - Original MVP specifications
- **[specs.v0.2.md](docs/specs.v0.2.md)** - Multi-provider and page tracking specifications

### Sprint Progress

| Sprint | Status      | Features                                     |
| ------ | ----------- | -------------------------------------------- |
| 1      | ✅ Complete | MVP: Extraction, chunking, ingestion, query  |
| 2      | ✅ Complete | Robustness: Error handling, logging, testing |
| 3      | ⏳ Planned  | Hybrid search, definitions, logging, formats |
| 4      | ⏳ Planned  | REST API (FastAPI), authentication, docs     |
| 5      | ⏳ Planned  | Docker, AWS ECS/Fargate, CI/CD, monitoring   |

______________________________________________________________________

## License

[Your License Here]

## Contributing

[Contributing Guidelines Here]

## Support

For questions or issues, please [open an issue](https://github.com/your-repo/issues).
