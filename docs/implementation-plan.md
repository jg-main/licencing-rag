# Implementation Plan - License Intelligence System

**Version:** 1.1 **Created:** 2026-01-26 **Updated:** 2026-01-27 **Target:** specs.v0.3.md

______________________________________________________________________

## Progress Checklist

> Update this checklist as tasks are completed. Use `[x]` to mark done.

### Sprint 1: MVP

#### 1.1 Critical Bug Fixes

- [x] Rename `promps.py` → `prompts.py`
- [x] Update import in `query.py`
- [x] Replace ChromaDB `Client` → `PersistentClient`
- [x] Remove deprecated `client.persist()` calls
- [x] Fix path: `RAW_DATA_DIR` to support provider subdirs

#### 1.2 Core Infrastructure

- [x] Create `app/embed.py` with `OllamaEmbeddingFunction`
- [x] Create `app/extract.py` with PDF page tracking
- [x] Add DOCX extraction support

#### 1.3 Chunking Improvements

- [x] Capture section headings in metadata
- [x] Track page numbers per chunk
- [x] Expand section detection regex patterns

#### 1.4 Pipeline Refactoring

- [x] Refactor `ingest.py` for multi-provider support
- [x] Refactor `query.py` with embedding function
- [x] Add provider-based collection naming

#### 1.5 CLI Implementation

- [x] Implement `main.py` with argparse
- [x] Add `ingest` command
- [x] Add `query` command
- [x] Add `list` command
- [ ] Create `app/cli.py` with main() entry point
- [ ] Add `[project.scripts]` to pyproject.toml for `rag` command
- [ ] Add `--format` flag for output (console/json)
- [ ] Update commands to use `rag` instead of `python main.py`

#### 1.6 Verification

- [x] Successfully ingest all 35 CME documents
- [x] Test query returns grounded answer with citations
- [x] Test refusal for out-of-scope questions
- [x] Response time < 15 seconds (14.4s achieved)

#### 1.7 Claude API Integration

- [x] Add `anthropic` to dependencies
- [x] Create `app/llm.py` with provider abstraction
- [x] Add `LLM_PROVIDER` config (ollama/anthropic)
- [x] Update `query.py` to use LLM abstraction
- [x] Test with Claude API (claude-sonnet-4-5-20250929)
- [x] Document API key setup in README

### Sprint 2: Robustness

- [x] Remove LangChain dependency entirely
- [x] Update `pyproject.toml`
- [x] Add `structlog` logging
- [x] Improve error handling (corrupted PDFs, Ollama down)
- [x] Enhance prompts with stricter guardrails
- [x] Add extraction quality validation
- [x] Document common issues in README

### Sprint 3: Enhancements

#### 3.1 Hybrid Search Implementation

- [ ] Add `rank-bm25` dependency to pyproject.toml
- [ ] Create `app/search.py` module
- [ ] Implement BM25 index building during ingestion
- [ ] Save BM25 index to `index/bm25/{provider}_index.pkl`
- [ ] Implement Reciprocal Rank Fusion (RRF) algorithm
- [ ] Update `query.py` to use hybrid search
- [ ] Add search mode parameter (vector/keyword/hybrid)
- [ ] Benchmark hybrid vs vector-only retrieval (target: >15% improvement)
- [ ] Add tests for hybrid ranking

#### 3.2 Definitions Auto-Linking

- [ ] Create `app/definitions.py` module
- [ ] Implement quoted term extraction from text
- [ ] Build definitions index (chunks with `is_definitions=true`)
- [ ] Implement definition retrieval by term matching
- [ ] Update prompt to include definitions section
- [ ] Add definition caching to reduce redundant retrievals
- [ ] Test with common defined terms (Subscriber, Redistribution, etc.)
- [ ] Update output format to include Definitions section

#### 3.3 Query Logging

- [ ] Create `app/logging_util.py` module
- [ ] Implement JSONL log writer
- [ ] Define log entry schema (query_id, timestamp, chunks, etc.)
- [ ] Add logging to query pipeline
- [ ] Implement log rotation (monthly)
- [ ] Add privacy controls (disable logging flag)
- [ ] Create `logs/` directory structure
- [ ] Add CLI command: `rag logs --tail N`
- [ ] Test log integrity and parsing

#### 3.4 Output Formats

- [ ] Create `app/output.py` module
- [ ] Implement console output formatter using Rich library
- [ ] Add panels, colors, and markdown styling for CLI
- [ ] Implement JSON output formatter
- [ ] Add structured JSON schema (answer, clauses, definitions, citations)
- [ ] Add `--format` flag to query command (console/json)
- [ ] Test both output formats
- [ ] Update documentation with format examples

#### 3.5 Integration & Testing

- [ ] Update all tests for hybrid search
- [ ] Add integration tests for definitions auto-linking
- [ ] Verify query logging doesn't impact performance
- [ ] Test output formatters (console and JSON)
- [ ] Document new features in README
- [ ] Update CLI help text with new options

### Sprint 4: REST API

#### 4.1 FastAPI Setup

- [ ] Add `fastapi` and `uvicorn` to pyproject.toml
- [ ] Create `api/` directory
- [ ] Create `api/__init__.py`
- [ ] Create `api/main.py` FastAPI application
- [ ] Create `api/routes.py` for endpoint definitions
- [ ] Configure CORS and middleware

#### 4.2 Query Endpoint

- [ ] Implement POST `/api/v1/query` endpoint
- [ ] Define request schema (question, providers, search_mode, top_k)
- [ ] Define response schema (answer, clauses, definitions, citations, metadata)
- [ ] Add input validation with Pydantic models
- [ ] Integrate with query.py business logic
- [ ] Add error handling and status codes

#### 4.3 Document & Stats Endpoints

- [ ] Implement GET `/api/v1/documents` endpoint
- [ ] Add provider filtering parameter
- [ ] Return document metadata (filename, path, pages, chunks)
- [ ] Implement GET `/api/v1/stats` endpoint
- [ ] Return system statistics (doc count, chunk count, index size)
- [ ] Add caching for expensive stats queries

#### 4.4 Admin Endpoints

- [ ] Implement POST `/api/v1/ingest/{provider}` endpoint
- [ ] Add background job queue for ingestion
- [ ] Return job_id and status for async tracking
- [ ] Implement GET `/api/v1/logs` endpoint
- [ ] Add pagination (limit, offset) for logs
- [ ] Add provider and date filtering

#### 4.5 Authentication & Security

- [ ] Implement API Key authentication (X-API-Key header)
- [ ] Add rate limiting (60 req/min default)
- [ ] Configure RATE_LIMIT_RPM environment variable
- [ ] Add request/response logging
- [ ] Implement health check endpoint GET `/health`
- [ ] Add API key management (optional for local dev)

#### 4.6 API Documentation & Testing

- [ ] Configure OpenAPI/Swagger UI (auto-generated)
- [ ] Add endpoint descriptions and examples
- [ ] Write integration tests for all endpoints
- [ ] Test authentication and rate limiting
- [ ] Test error responses (400, 401, 404, 500)
- [ ] Performance testing (load, concurrent requests)
- [ ] CLI command: `rag serve --port 8000 --host 0.0.0.0`

### Sprint 5: AWS Deployment

#### 5.1 Docker Containerization

- [ ] Create `docker/Dockerfile`
- [ ] Configure multi-stage build (builder + runtime)
- [ ] Optimize image size (\<1GB)
- [ ] Create `docker/docker-compose.yml` for local dev
- [ ] Add `.dockerignore` file
- [ ] Test local container build
- [ ] Test local container run with volume mounts
- [ ] Document environment variables

#### 5.2 AWS Infrastructure Setup

- [ ] Create AWS account / configure IAM
- [ ] Set up VPC with public/private subnets
- [ ] Configure security groups (ALB, ECS)
- [ ] Create EFS file system for persistent storage
- [ ] Set up ECR repository for Docker images
- [ ] Create ECS cluster (Fargate)
- [ ] Configure Application Load Balancer
- [ ] Set up ACM certificate for HTTPS
- [ ] Configure Route53 DNS (optional)

#### 5.3 ECS Task Definition

- [ ] Create task definition JSON
- [ ] Configure CPU/Memory (2 vCPU, 4 GB)
- [ ] Mount EFS volumes (/data, /index, /logs)
- [ ] Set environment variables
- [ ] Configure Secrets Manager for API keys
- [ ] Set health check endpoint
- [ ] Configure logging (CloudWatch)
- [ ] Test task execution manually

#### 5.4 ECS Service Configuration

- [ ] Create ECS service
- [ ] Configure auto-scaling (min: 1, max: 3)
- [ ] Set up ALB target group
- [ ] Configure health checks
- [ ] Test load balancing
- [ ] Configure blue/green deployment
- [ ] Set up CloudWatch alarms (CPU, memory, errors)

#### 5.5 CI/CD Pipeline

- [ ] Create `.github/workflows/deploy.yml`
- [ ] Add GitHub secrets (AWS credentials)
- [ ] Implement test stage (pytest)
- [ ] Implement build stage (Docker)
- [ ] Implement push stage (ECR)
- [ ] Implement deploy stage (ECS update)
- [ ] Add deployment notifications (Slack/email)
- [ ] Test full pipeline end-to-end
- [ ] Document rollback procedure

#### 5.6 Monitoring & Operations

- [ ] Set up CloudWatch dashboard
- [ ] Configure log aggregation
- [ ] Set up cost monitoring
- [ ] Create runbook for common issues
- [ ] Document backup/restore procedures
- [ ] Test disaster recovery scenario
- [ ] Create operational metrics (uptime, query latency)
- [ ] Set up alerting rules

### Future: Multi-Provider

- [ ] OpenAI API support (alternative to Claude)
- [ ] Add other providers (OPRA, CTA, UTP)
- [ ] Test cross-provider queries
- [ ] Add provider-aware prompt formatting
- [ ] Update documentation for multi-provider usage

______________________________________________________________________

## Executive Summary

This plan outlines a phased approach to build a working local RAG system for license agreement analysis. The plan prioritizes getting a minimal working system first, then iterating to add robustness and features.

**Estimated Timeline:** 2-3 weeks for Phase 1 (MVP)

______________________________________________________________________

## Current State Assessment

### What Exists

| Component | Status | Issues | |-----------|--------|--------| | Project structure | ✅ Good | Clean separation | | Dependencies | ⚠️ Partial | LangChain unnecessary | | Config | ✅ Good | Needs path updates | | PDF extraction | ⚠️ Partial | Missing page tracking | | Chunking | ⚠️ Partial | Missing metadata capture | | Ingestion | ❌ Broken | ChromaDB API outdated | | Query | ❌ Broken | Missing embedding function | | CLI | ❌ Missing | Placeholder only | | Prompts | ✅ Good | Minor rename needed |

### Blocking Issues (Must Fix First)

1. ChromaDB uses deprecated `Client()` — must use `PersistentClient()`
1. Query doesn't embed the question — missing embedding function
1. Path mismatch — code looks at `data/raw/` but docs are in `data/raw/cme/`
1. Filename typo — `promps.py` should be `prompts.py`

______________________________________________________________________

## Phase 1: Minimal Working System (Week 1)

**Goal:** End-to-end query working with CME documents

### 1.1 Fix Critical Bugs (Day 1)

#### Task 1.1.1: Rename prompts file

```bash
mv app/promps.py app/prompts.py
```

Update import in `query.py`.

#### Task 1.1.2: Update ChromaDB client usage

Replace deprecated pattern:

```python
# OLD (broken)
from chromadb import Client
from chromadb.config import Settings
client = Client(Settings(persist_directory=CHROMA_DIR))
client.persist()

# NEW (correct)
import chromadb
client = chromadb.PersistentClient(path=CHROMA_DIR)
# No persist() call needed — auto-persists
```

#### Task 1.1.3: Add embedding function for queries

ChromaDB needs to know how to embed query text:

```python
import ollama

class OllamaEmbeddingFunction:
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings = []
        for text in input:
            response = ollama.embed(model=self.model, input=text)
            embeddings.append(response["embeddings"][0])
        return embeddings
```

#### Task 1.1.4: Update config paths

```python
RAW_DATA_DIR = "data/raw"  # Base path, iterate subdirs
PROVIDERS = ["cme"]        # Active providers
```

### 1.2 Refactor Extraction (Day 2)

#### Task 1.2.1: Create `app/extract.py`

Consolidate extraction logic with page tracking:

```python
def extract_pdf(path: Path) -> tuple[str, dict]:
    """Extract text and metadata from PDF."""
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pages.append({
            "page_num": page.number + 1,
            "text": page.get_text()
        })
    return pages, {"page_count": len(pages)}

def extract_docx(path: Path) -> tuple[str, dict]:
    """Extract text from DOCX."""
    # Implementation
```

#### Task 1.2.2: Track page boundaries in chunks

Pass page info through chunking so each chunk knows its source pages.

### 1.3 Improve Chunking (Day 2-3)

#### Task 1.3.1: Capture section headings

```python
def chunk_document(pages: list[dict], filename: str, provider: str) -> list[dict]:
    """Chunk document with full metadata."""
    # Return list of:
    # {
    #     "text": str,
    #     "metadata": {
    #         "chunk_id": str,
    #         "provider": str,
    #         "document_name": str,
    #         "section_heading": str,
    #         "page_start": int,
    #         "page_end": int,
    #         ...
    #     }
    # }
```

#### Task 1.3.2: Improve section detection

Expand regex patterns per specs:

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

### 1.4 Rebuild Ingestion Pipeline (Day 3-4)

#### Task 1.4.1: Refactor `ingest.py`

```python
def ingest_provider(provider: str) -> None:
    """Ingest all documents for a provider."""
    raw_dir = Path(RAW_DATA_DIR) / provider

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = OllamaEmbeddingFunction()

    collection = client.get_or_create_collection(
        name=f"{provider}_docs",
        embedding_function=embed_fn,
    )

    # Clear existing for re-ingestion
    # Process each document
    # Add chunks with metadata
```

#### Task 1.4.2: Add progress tracking

Use tqdm for visibility during long ingestion runs.

### 1.5 Fix Query Pipeline (Day 4)

#### Task 1.5.1: Update `query.py`

```python
def query(question: str, providers: list[str] = None) -> str:
    """Query the knowledge base."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embed_fn = OllamaEmbeddingFunction()

    results = []
    for provider in (providers or PROVIDERS):
        collection = client.get_collection(
            name=f"{provider}_docs",
            embedding_function=embed_fn,
        )
        provider_results = collection.query(
            query_texts=[question],
            n_results=TOP_K,
        )
        results.extend(zip(
            provider_results["documents"][0],
            provider_results["metadatas"][0],
        ))

    # Build context and call LLM
```

### 1.5 Build CLI (Day 5)

#### Task 1.5.1: Implement `main.py` with argparse

```python
def main():
    parser = argparse.ArgumentParser(
        description="License Intelligence System"
    )
    subparsers = parser.add_subparsers(dest="command")

    # ingest command
    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--provider", required=True)

    # query command
    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("question")
    query_parser.add_argument("--provider", action="append")

    # list command
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--provider")

    args = parser.parse_args()
    # Dispatch to handlers
```

### 1.6 Verification (Day 5)

#### Test Cases

| Test                                | Expected                      |
| ----------------------------------- | ----------------------------- |
| `rag ingest --provider cme`         | Ingests 35 docs, no errors    |
| `rag list --provider cme`           | Shows 35 documents            |
| `rag query "What is a subscriber?"` | Returns answer with citations |
| `rag query "What is Bitcoin?"`      | Returns refusal message       |

### 1.7 Claude API Integration (Day 6)

**Goal:** Use Claude API for answer generation (better quality, faster for dev)

#### Architecture Decision

| Component | Tool | Reason | |-----------|------|--------| | Embeddings | Ollama (nomic-embed-text) | Free, fast, runs locally | | Answer Generation | Claude API | Better quality, no GPU needed | | Vector Storage | ChromaDB | Local, persistent |

#### Task 1.7.1: Add anthropic dependency

```bash
uv add anthropic
```

#### Task 1.7.2: Create `app/llm.py`

```python
# app/llm.py
"""LLM provider abstraction for answer generation."""

import os
from abc import ABC, abstractmethod

import anthropic
import ollama

from app.config import LLM_MODEL, LLM_PROVIDER


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system: str, prompt: str) -> str:
        """Generate a response given system prompt and user prompt."""
        pass


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = LLM_MODEL):
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        response = ollama.generate(
            model=self.model,
            system=system,
            prompt=prompt,
        )
        return response["response"]


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def get_llm() -> LLMProvider:
    """Get the configured LLM provider."""
    if LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    return OllamaProvider()
```

#### Task 1.7.3: Update config

```python
# app/config.py
import os

# LLM Provider: "ollama" or "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# For Ollama
LLM_MODEL = "llama3.2:3b"  # or llama3.1:8b with more RAM

# For Anthropic (uses ANTHROPIC_API_KEY env var)
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
```

#### Task 1.7.4: Usage

```bash
# Use Ollama (default, free but slow on limited hardware)
rag query "What are the CME fees?"

# Use Claude API (fast, ~$0.003/query)
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"
rag query "What are the CME fees?"
```

#### Cost Estimate (Claude API)

| Usage | Tokens/query | Cost/query | Monthly (100 queries/day) | |-------|--------------|------------|---------------------------| | Light | ~2,000 | ~$0.003 | ~$9 | | Heavy | ~5,000 | ~$0.008 | ~$24 |

______________________________________________________________________

## Phase 3: Enhanced Features (Sprint 3)

**Goal:** Improve retrieval quality and add query logging

### 3.1 Hybrid Search (BM25 + Vector)

Combine semantic (vector) and keyword (BM25) search for better retrieval coverage.

**Benefits:**

- Better handling of exact keyword matches
- Improved recall for technical terms
- More robust against embedding model limitations

**Implementation:**

```python
from rank_bm25 import BM25Okapi

# Build BM25 index during ingestion
tokenized_corpus = [chunk["text"].split() for chunk in chunks]
bm25 = BM25Okapi(tokenized_corpus)

# Query with hybrid approach
vector_results = chroma_collection.query(question, n_results=10)
bm25_scores = bm25.get_scores(question.split())

# Reciprocal Rank Fusion (RRF)
def rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)

# Combine and re-rank
combined_scores = merge_results(vector_results, bm25_scores, rrf_score)
top_chunks = sorted(combined_scores, reverse=True)[:5]
```

### 3.2 Definitions Auto-Linking

Automatically retrieve and include definitions when query response contains defined terms.

**Detection:**

- Quoted terms in response (e.g., "Subscriber")
- Initial caps technical terms
- Terms in definitions index

**Implementation:**

```python
# Build definitions index (chunks with is_definitions=true)
definitions_index = {
    "subscriber": chunk_id,
    "redistribution": chunk_id,
    ...
}

# After LLM generates answer, scan for terms
quoted_terms = re.findall(r'"([^"]+)"', answer)

# Retrieve definitions
definitions = [
    retrieve_chunk(definitions_index[term.lower()])
    for term in quoted_terms
    if term.lower() in definitions_index
]

# Add to response
response += "\n\n## Definitions\n\n"
for defn in definitions:
    response += f"> **{term}**: {defn.text}\n"
```

### 3.3 Query Logging

Log all queries to JSONL for audit, analysis, and compliance.

**Schema:**

```json
{
  "timestamp": "2026-01-27T14:30:00Z",
  "query_id": "uuid",
  "question": "What are CME fees?",
  "providers": ["cme"],
  "vector_chunks": ["id1", "id2"],
  "bm25_chunks": ["id2", "id3"],
  "final_chunks": ["id2", "id1", "id3"],
  "definitions_linked": ["Fee", "Subscriber"],
  "answer_length": 342,
  "response_time_ms": 2847,
  "llm_provider": "anthropic",
  "error": null
}
```

**Privacy:**

- Local storage only
- No PII beyond query text
- Monthly rotation
- Configurable disable flag

### 3.4 Output Formats

Support two output modes for different use cases.

**Console Output (using Rich):**

```python
from rich.console import Console
from rich.panel import Panel

console = Console()
console.print(Panel(answer_text, title="Answer", border_style="blue"))
console.print(f'> [bold]{citation.document}[/bold] (Page {citation.page})')
```

**JSON Output:**

```json
{
  "answer": "Clear, concise answer...",
  "supporting_clauses": [...],
  "definitions": [...],
  "citations": [...],
  "metadata": {...}
}
```

**CLI Usage:**

```bash
rag query --format console "What are the fees?"  # default
rag query --format json "What are the fees?" > result.json
```

______________________________________________________________________

## Phase 4: REST API (Sprint 4)

**Goal:** Provide programmatic API for integration and remote access

### 4.1 Technology Choice: FastAPI

**Rationale:**

- Fast, modern Python framework
- Auto-generated OpenAPI documentation
- Built-in data validation (Pydantic)
- High performance (ASGI server)
- Easy to test and extend

### 4.2 Core Endpoints

#### Query Endpoint

- POST `/api/v1/query`
- Request: question, providers, search_mode, top_k, include_definitions
- Response: answer, supporting_clauses, definitions, citations, metadata
- Error handling: 400 (validation), 500 (processing)

#### Document & Stats Endpoints

- GET `/api/v1/documents?provider={provider}`
- GET `/api/v1/stats`
- Response: document metadata, system statistics

#### Admin Endpoints

- POST `/api/v1/ingest/{provider}` — Trigger re-ingestion
- GET `/api/v1/logs?limit={limit}&offset={offset}` — Query logs

#### Health Check

- GET `/health` — Load balancer health check

### 4.3 API Considerations

- **Authentication** — API Key header (X-API-Key)
- **Rate limiting** — 60 req/min default
- **CORS** — Configurable allowed origins
- **Error handling** — Consistent error response format
- **Documentation** — Auto-generated Swagger UI

______________________________________________________________________

## Phase 5: Cloud Deployment (Sprint 5)

**Goal:** Deploy to AWS for team access and higher availability

### 5.1 Architecture Overview

```
Internet → Route53 → ALB (HTTPS) → ECS Fargate → EFS (storage)
                                        ↓
                                  CloudWatch Logs
```

### 5.2 Resource Specifications

| Resource    | Spec         | Cost (monthly) |
| ----------- | ------------ | -------------- |
| ECS Fargate | 2 vCPU, 4 GB | ~$35           |
| ALB         | 1 instance   | ~$20           |
| EFS         | 20 GB        | ~$6            |
| ECR         | \<1 GB       | ~$1            |
| **Total**   |              | **~$62/month** |

### 5.3 Deployment Strategy

**Blue/Green Deployment:**

1. Push new Docker image to ECR
1. ECS creates new task with new image
1. ALB routes traffic to new task
1. Health checks pass → old task terminated
1. Health checks fail → rollback to old task

**CI/CD Pipeline:**

- **Trigger**: Push to `main` branch
- **Test**: Run pytest suite
- **Build**: Docker image build
- **Push**: Upload to ECR
- **Deploy**: ECS service update
- **Notify**: Slack/email notification

### 5.4 Monitoring & Alerting

**CloudWatch Metrics:**

- CPU/Memory utilization (threshold: >80%)
- Request count (track usage patterns)
- Error rate (threshold: >5%)
- Query latency (threshold: >10s)

**Alarms:**

- High CPU → Auto-scale up
- Low CPU → Auto-scale down
- High error rate → SNS notification
- Health check failures → Automatic rollback

### 5.5 Security Considerations

- **VPC**: Private subnets for ECS tasks
- **Secrets**: AWS Secrets Manager for API keys
- **HTTPS**: ACM certificate on ALB
- **IAM**: Least-privilege task role
- **Network**: Security groups for egress control

______________________________________________________________________

## Phase 2: Robustness & Quality (Week 2)

**Goal:** Production-quality ingestion and better answers

### 2.1 Remove LangChain Dependency

Replace `langchain_community` usage with direct `ollama` package calls.

```python
# OLD
from langchain_community.llms import Ollama
llm = Ollama(model=LLM_MODEL)
response = llm(prompt)

# NEW
import ollama
response = ollama.generate(model=LLM_MODEL, prompt=prompt)
answer = response["response"]
```

### 2.2 Improve Text Extraction Quality

- Handle PDFs with complex layouts (multi-column)
- Detect and skip headers/footers
- Preserve tables as structured text
- Add extraction quality report

### 2.3 Enhance Prompts

```python
SYSTEM_PROMPT = """
You are a legal analysis assistant specializing in market data licensing.

STRICT RULES:
1. Answer ONLY using the provided context
2. NEVER use external knowledge
3. ALWAYS cite specific documents and sections
4. If the answer is not in the context, respond exactly:
   "This is not addressed in the provided {provider} documents."

FORMAT:
- Start with a direct answer
- Quote relevant clauses
- List all citations at the end
"""
```

### 2.4 Add Logging

```python
import structlog

log = structlog.get_logger()

log.info("ingesting_document",
    provider=provider,
    filename=filename,
    chunk_count=len(chunks)
)
```

### 2.5 Error Handling

- Graceful handling of corrupted PDFs
- Retry logic for Ollama connection
- Clear error messages for missing providers

______________________________________________________________________

## Phase 3: Enhanced Features (Sprint 3)

**Goal:** Improve retrieval quality and add query logging

### 4.1 Hybrid Search

Add BM25 keyword search alongside vector search:

```python
from rank_bm25 import BM25Okapi

# Combine scores:
# final_score = alpha * vector_score + (1 - alpha) * bm25_score
```

### 4.2 Definitions Auto-Linking

When a retrieved chunk contains a defined term (in quotes or initial caps), automatically retrieve the definition chunk.

### 4.3 Query Logging

```python
# logs/queries.jsonl
{
    "timestamp": "2026-01-26T14:30:00Z",
    "question": "What are redistribution requirements?",
    "providers": ["cme"],
    "chunks_retrieved": ["cme_ila-guide_12", "cme_schedule-2_5"],
    "answer_length": 342
}
```

### 4.4 CTA/UTP Support

Same pattern as OPRA addition.

______________________________________________________________________

## Task Checklist

### Phase 1 (MVP) - ✅ COMPLETE

- [x] Rename `promps.py` → `prompts.py`
- [x] Update imports in `query.py`
- [x] Replace ChromaDB `Client` with `PersistentClient`
- [x] Remove `client.persist()` calls
- [x] Create `OllamaEmbeddingFunction` class
- [x] Create `app/extract.py` with page tracking
- [x] Add DOCX extraction support
- [x] Update chunking to capture section headings
- [x] Update chunking to track page numbers
- [x] Refactor `ingest.py` for provider support
- [x] Refactor `query.py` with embedding function
- [x] Implement CLI in `main.py`
- [x] Test end-to-end with CME docs
- [x] Update `pyproject.toml` (remove langchain)
- [x] Add subdirectory support (Fees/, Agreements/)
- [x] Add comprehensive test coverage (75 tests)

### Phase 2 (Robustness) - ✅ COMPLETE

- [x] Remove all LangChain usage
- [x] Add structlog logging
- [x] Improve error handling
- [x] Enhance prompts with stricter guardrails
- [x] Add extraction quality checks
- [x] Document common issues

### Phase 3 (Enhancements) - Sprint 3

- [ ] **Hybrid Search**

  - [ ] Add rank-bm25 dependency
  - [ ] Create app/search.py module
  - [ ] Implement BM25 indexing
  - [ ] Implement RRF algorithm
  - [ ] Update query pipeline
  - [ ] Add tests and benchmarks

- [ ] **Definitions Auto-Linking**

  - [ ] Create app/definitions.py module
  - [ ] Build definitions index
  - [ ] Implement term extraction
  - [ ] Integrate with query pipeline
  - [ ] Update prompts and output format

- [ ] **Query Logging**

  - [ ] Create app/logging_util.py module
  - [ ] Implement JSONL writer
  - [ ] Add privacy controls
  - [ ] Create CLI logs viewer
  - [ ] Test log integrity

### Phase 4 (REST API) - Sprint 4

- [ ] **FastAPI Setup**

  - [ ] Add fastapi and uvicorn dependencies
  - [ ] Create api/ directory structure
  - [ ] Configure CORS and middleware

- [ ] **Core API Endpoints**

  - [ ] Query endpoint (POST /api/v1/query)
  - [ ] Document listing (GET /api/v1/documents)
  - [ ] Stats endpoint (GET /api/v1/stats)
  - [ ] Ingestion trigger (POST /api/v1/ingest/{provider})
  - [ ] Logs endpoint (GET /api/v1/logs)
  - [ ] Health check (GET /health)

- [ ] **Security & Testing**

  - [ ] API Key authentication
  - [ ] Rate limiting
  - [ ] OpenAPI documentation
  - [ ] Integration tests

### Phase 5 (Deployment) - Sprint 5

- [ ] **Docker**

  - [ ] Create Dockerfile
  - [ ] Create docker-compose.yml
  - [ ] Test local container
  - [ ] Optimize image size

- [ ] **AWS Infrastructure**

  - [ ] VPC and security groups
  - [ ] ECS Fargate cluster
  - [ ] Application Load Balancer
  - [ ] EFS persistent storage
  - [ ] Secrets Manager setup

- [ ] **CI/CD**

  - [ ] GitHub Actions workflow
  - [ ] ECR image push
  - [ ] ECS deployment
  - [ ] Health checks and rollback

- [ ] **Monitoring**

  - [ ] CloudWatch dashboard
  - [ ] Alerting rules
  - [ ] Log aggregation
  - [ ] Runbook creation

### Future (Multi-Provider)

- [ ] Collect OPRA documents
- [ ] Ingest OPRA documents
- [ ] Test cross-provider queries
- [ ] Add OpenAI API support
- [ ] Update documentation

______________________________________________________________________

## Risk Register

| Risk | Impact | Mitigation | |------|--------|------------| | Ollama not running | Blocking | Check at startup, clear error message | | PDF extraction quality | Medium | Manual review of first batch, add fallbacks | | Embedding dimension mismatch | Blocking | Use same model for ingest and query | | ChromaDB corruption | High | Add backup before re-ingestion | | Large document set (>1000) | Medium | Batch ingestion, progress tracking |

______________________________________________________________________

## Definition of Done

Phase 1 is complete when:

1. `rag ingest --provider cme` runs without errors
1. `rag query "question"` returns grounded answers
1. Citations include document name and section
1. Refusal works for out-of-scope questions
1. All 35 CME documents are indexed
1. Response time < 15 seconds on standard hardware

______________________________________________________________________

## Next Actions

1. **Immediate:** Fix blocking bugs (1.1.1 - 1.1.4)
1. **Today:** Run first successful ingest
1. **This week:** Complete Phase 1 MVP
1. **Next week:** Begin Phase 2 hardening
