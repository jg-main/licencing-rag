# Implementation Plan - License Intelligence System

**Version:** 1.0 **Created:** 2026-01-26 **Target:** specs.v0.2.md

______________________________________________________________________

## Progress Checklist

> Update this checklist as tasks are completed. Use `[x]` to mark done.

### Phase 1: MVP (Week 1)

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

#### 1.6 Verification

- [x] Successfully ingest all 35 CME documents
- [x] Test query returns grounded answer with citations
- [ ] Test refusal for out-of-scope questions
- [ ] Response time < 15 seconds

#### 1.7 Claude API Integration

- [x] Add `anthropic` to dependencies
- [x] Create `app/llm.py` with provider abstraction
- [x] Add `LLM_PROVIDER` config (ollama/anthropic)
- [x] Update `query.py` to use LLM abstraction
- [ ] Test with Claude API
- [x] Document API key setup in README

### Phase 2: Robustness (Week 2)

- [x] Remove LangChain dependency entirely
- [x] Update `pyproject.toml`
- [ ] Add `structlog` logging
- [ ] Improve error handling (corrupted PDFs, Ollama down)
- [ ] Enhance prompts with stricter guardrails
- [ ] Add extraction quality validation
- [ ] Document common issues in README

### Phase 3: Multi-Provider (Week 3)

- [ ] Collect OPRA license documents
- [ ] Place in `data/raw/opra/`
- [ ] Ingest OPRA documents
- [ ] Test cross-provider queries
- [ ] Add provider-aware prompt formatting
- [ ] Update documentation for multi-provider usage

### Phase 4: Enhancements (Future)

- [ ] Hybrid search (BM25 + vector)
- [ ] Definitions auto-linking
- [ ] Query logging to `logs/queries.jsonl`
- [ ] CTA/UTP document support
- [ ] Web UI (Streamlit)
- [ ] OpenAI API support (alternative to Claude)

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

| Test | Expected | |------|----------| | `python main.py ingest --provider cme` | Ingests 35 docs, no errors | | `python main.py list --provider cme` | Shows 35 documents | | `python main.py query "What is a subscriber?"` | Returns answer with citations | | `python main.py query "What is Bitcoin?"` | Returns refusal message |

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
python main.py query "What are the CME fees?"

# Use Claude API (fast, ~$0.003/query)
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"
python main.py query "What are the CME fees?"
```

#### Cost Estimate (Claude API)

| Usage | Tokens/query | Cost/query | Monthly (100 queries/day) | |-------|--------------|------------|---------------------------| | Light | ~2,000 | ~$0.003 | ~$9 | | Heavy | ~5,000 | ~$0.008 | ~$24 |

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

## Phase 3: Multi-Provider Support (Week 3)

**Goal:** Add OPRA documents, validate extensibility

### 3.1 OPRA Document Collection

- Gather OPRA license agreements
- Place in `data/raw/opra/`
- Verify extraction quality

### 3.2 Provider Configuration

```python
# config.py
PROVIDERS = {
    "cme": {
        "name": "CME Group",
        "collection": "cme_docs",
        "raw_dir": "data/raw/cme",
    },
    "opra": {
        "name": "OPRA",
        "collection": "opra_docs",
        "raw_dir": "data/raw/opra",
    },
}
```

### 3.3 Cross-Provider Query

```bash
python main.py query --provider cme --provider opra \
    "What are the subscriber reporting requirements?"
```

### 3.4 Provider-Aware Prompts

Adjust prompts to clarify which provider's documents are being cited.

______________________________________________________________________

## Phase 4: Enhanced Features (Future)

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

### Phase 1 (MVP)

- [ ] Rename `promps.py` → `prompts.py`
- [ ] Update imports in `query.py`
- [ ] Replace ChromaDB `Client` with `PersistentClient`
- [ ] Remove `client.persist()` calls
- [ ] Create `OllamaEmbeddingFunction` class
- [ ] Create `app/extract.py` with page tracking
- [ ] Add DOCX extraction support
- [ ] Update chunking to capture section headings
- [ ] Update chunking to track page numbers
- [ ] Refactor `ingest.py` for provider support
- [ ] Refactor `query.py` with embedding function
- [ ] Implement CLI in `main.py`
- [ ] Test end-to-end with CME docs
- [ ] Update `pyproject.toml` (remove langchain)

### Phase 2 (Robustness)

- [ ] Remove all LangChain usage
- [ ] Add structlog logging
- [ ] Improve error handling
- [ ] Enhance prompts with stricter guardrails
- [ ] Add extraction quality checks
- [ ] Document common issues

### Phase 3 (Multi-Provider)

- [ ] Collect OPRA documents
- [ ] Ingest OPRA documents
- [ ] Test cross-provider queries
- [ ] Update documentation

______________________________________________________________________

## Risk Register

| Risk | Impact | Mitigation | |------|--------|------------| | Ollama not running | Blocking | Check at startup, clear error message | | PDF extraction quality | Medium | Manual review of first batch, add fallbacks | | Embedding dimension mismatch | Blocking | Use same model for ingest and query | | ChromaDB corruption | High | Add backup before re-ingestion | | Large document set (>1000) | Medium | Batch ingestion, progress tracking |

______________________________________________________________________

## Definition of Done

Phase 1 is complete when:

1. `python main.py ingest --provider cme` runs without errors
1. `python main.py query "question"` returns grounded answers
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
