# Implementation Plan - License Intelligence System (OpenAI Branch)

**Version:** 2.0\
**Created:** 2026-01-26\
**Updated:** 2026-01-28\
**Target:** specs.v0.4.md\
**Branch:** openai

______________________________________________________________________

## Overview

This branch implements a new approach using **OpenAI as the single provider** for both embeddings and LLM reasoning. This is a significant departure from the previous Ollama/Claude hybrid approach.

### Key Changes from v1.x

- **Single Provider**: OpenAI only (no Ollama, no Claude)
- **New Embeddings**: `text-embedding-3-large` (3072 dimensions vs 768)
- **New LLM**: `gpt-4.1` for both answer generation and reranking
- **Query Normalization**: Pre-retrieval query processing
- **LLM Reranking**: Score chunks with GPT-4.1 before answer generation
- **Confidence Gating**: Code-enforced refusal when evidence is weak
- **Context Budget**: Enforce ≤60k token limit
- **Debug Mode**: Full transparency into retrieval pipeline
- **Evaluation Set**: Validate clause retrieval accuracy

______________________________________________________________________

## Progress Checklist

> Update this checklist as tasks are completed. Use `[x]` to mark done.

### Phase 1: OpenAI Embeddings Upgrade

#### 1.1 Dependencies & Configuration

- [ ] Add `openai` package to pyproject.toml
- [ ] Add `tiktoken` package for token counting
- [ ] Remove `anthropic` package (no longer needed)
- [ ] Remove `ollama` package (no longer needed)
- [ ] Update `app/config.py` with OpenAI model constants
- [ ] Remove `LLM_PROVIDER` abstraction (single provider)

#### 1.2 Embedding Function Rewrite

- [ ] Rewrite `app/embed.py` for OpenAI embeddings
- [ ] Use `text-embedding-3-large` model (3072 dimensions)
- [ ] Implement batch embedding for efficiency
- [ ] Add error handling for API failures
- [ ] Update ChromaDB dimension configuration

#### 1.3 LLM Provider Rewrite

- [ ] Rewrite `app/llm.py` for OpenAI only
- [ ] Remove `OllamaProvider` class
- [ ] Remove `AnthropicProvider` class
- [ ] Implement `OpenAIProvider` with `gpt-4.1`
- [ ] Remove provider abstraction (direct OpenAI client)

#### 1.4 Index Migration

- [ ] Delete existing ChromaDB index (incompatible dimensions)
- [ ] Delete existing BM25 index
- [ ] Re-ingest all documents with new embeddings
- [ ] Store embedding model metadata with index
- [ ] Add version check: block queries if model mismatch

#### 1.5 Verification

- [ ] Test embedding generation
- [ ] Test basic query without reranking
- [ ] Verify identical queries return consistent results
- [ ] Document API key setup

### Phase 2: Query Normalization

#### 2.1 Implementation

- [ ] Create `app/normalize.py` module
- [ ] Implement `normalize_query()` function
- [ ] Strip leading phrases ("what is", "can you", etc.)
- [ ] Remove filler words (the, a, an, is, etc.)
- [ ] Preserve nouns and legal terms
- [ ] Add comprehensive test cases

#### 2.2 Integration

- [ ] Update `query.py` to normalize before embedding
- [ ] Update `query.py` to normalize before BM25
- [ ] Log original vs normalized query
- [ ] Add `--debug` flag to show normalization

#### 2.3 Verification

- [ ] Test: "What is the fee schedule?" → "fee schedule"
- [ ] Test: Normalized query retrieves same top chunks as keyword query
- [ ] Verify fee schedules, exhibits, tables are retrievable

### Phase 3: Hybrid Retrieval (Mandatory)

> Note: Hybrid search already exists from v1.x, but needs verification with new embeddings.

#### 3.1 Verification with OpenAI Embeddings

- [ ] Test vector search with `text-embedding-3-large`
- [ ] Verify BM25 still works correctly
- [ ] Test RRF merge produces reasonable rankings
- [ ] Verify candidate pool max 12 chunks

#### 3.2 Configuration Updates

- [ ] Set vector k=10
- [ ] Set BM25 k=10
- [ ] Ensure deduplication by chunk_id
- [ ] Log retrieval sources in debug mode

### Phase 4: LLM Reranking

#### 4.1 Implementation

- [ ] Create `app/rerank.py` module
- [ ] Implement scoring prompt (0-3 relevance scale)
- [ ] Implement `rerank_chunks()` function
- [ ] Call GPT-4.1 for each candidate chunk
- [ ] Sort by score, keep top 3-5

#### 4.2 Integration

- [ ] Update `query.py` to call reranking after retrieval
- [ ] Log scores in debug mode
- [ ] Track dropped chunks with reasons

#### 4.3 Optimization

- [ ] Truncate chunk text to ~2000 chars for reranking
- [ ] Consider parallel API calls for speed
- [ ] Add timeout handling

### Phase 5: Context Budget Enforcement

#### 5.1 Implementation

- [ ] Add `tiktoken` for accurate token counting
- [ ] Implement `enforce_context_budget()` function
- [ ] Target: ≤60k tokens for LLM input
- [ ] Prefer shorter, higher-score chunks
- [ ] Drop long, low-score chunks first

#### 5.2 Integration

- [ ] Apply budget after reranking
- [ ] Log final context token count
- [ ] Add budget exceeded warning

### Phase 6: Retrieval Confidence Gating

#### 6.1 Implementation

- [ ] Create `app/gate.py` module
- [ ] Define `RELEVANCE_THRESHOLD = 2`
- [ ] Define `CONFIDENCE_THRESHOLD = 2`
- [ ] Implement `should_refuse()` function
- [ ] Return standard refusal message

#### 6.2 Rules (Code-Enforced)

- [ ] Refuse if no chunk score ≥ 2
- [ ] Refuse if top score < 2
- [ ] Refuse if all chunks score 0-1
- [ ] Log refusal reason in debug mode

#### 6.3 Integration

- [ ] Update `query.py` to gate before LLM call
- [ ] Skip LLM call entirely on refusal
- [ ] Return deterministic refusal message

### Phase 7: LLM Prompt Discipline

#### 7.1 System Prompt Update

- [ ] Update `app/prompts.py` with strict rules
- [ ] Emphasize: use ONLY provided context
- [ ] Emphasize: NEVER extrapolate
- [ ] Enforce: mandatory citations
- [ ] Add explicit refusal instruction

#### 7.2 Output Format

- [ ] Enforce: "Answer: <text>" format
- [ ] Enforce: "Citations: <list>" format
- [ ] Test refusal message consistency

### Phase 8: Debug & Audit Mode

#### 8.1 Implementation

- [ ] Add `--debug` flag to CLI
- [ ] Log original query
- [ ] Log normalized query
- [ ] Log retrieved chunks with ranks
- [ ] Log rerank scores
- [ ] Log dropped chunks with reasons
- [ ] Log final context token count
- [ ] Log confidence gate result

#### 8.2 Output Format

- [ ] JSON format for debug output
- [ ] Write to stderr (separate from answer)
- [ ] Include all relevant metadata

### Phase 9: Evaluation Set

#### 9.1 Create Evaluation Set

- [ ] Create `eval/` directory
- [ ] Create `eval/questions.json`
- [ ] Add ~20 representative questions
- [ ] Include expected chunks
- [ ] Include expected refusal cases

#### 9.2 Evaluation Script

- [ ] Create `eval/run_eval.py`
- [ ] Implement chunk recall metric
- [ ] Implement refusal accuracy metric
- [ ] Generate evaluation report

#### 9.3 Targets

- [ ] Chunk Recall ≥ 90%
- [ ] Refusal Accuracy = 100%
- [ ] False Refusal Rate < 5%

### Phase 10: Cleanup & Documentation

#### 10.1 Remove Legacy Code

- [ ] Delete Ollama-specific code
- [ ] Delete Anthropic-specific code
- [ ] Delete LLM provider abstraction
- [ ] Remove unused imports
- [ ] Update all docstrings

#### 10.2 Documentation

- [ ] Update README.md for OpenAI setup
- [ ] Document environment variables
- [ ] Document debug mode usage
- [ ] Add cost estimation section
- [ ] Update CLI help text

#### 10.3 Testing

- [ ] Update all existing tests
- [ ] Add tests for normalization
- [ ] Add tests for reranking
- [ ] Add tests for gating
- [ ] Run full test suite

______________________________________________________________________

## Legacy Sections (Completed in v1.x - Reference Only)

The following sections document work completed in the master branch. They are kept for reference but are not part of the OpenAI branch implementation.

<details>
<summary>Click to expand legacy Sprint 1-3 details</summary>

### Sprint 1: MVP (Completed)

#### 1.1 Critical Bug Fixes

- [x] Rename `prompts.py` → `prompts.py`
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
- [x] Create `app/cli.py` with main() entry point
- [x] Add `[project.scripts]` to pyproject.toml for `rag` command
- [x] Add `--format` flag for output (console/json)
- [x] Update commands to use `rag` instead of `python main.py`

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

### Sprint 2: Robustness (Completed)

- [x] Remove LangChain dependency entirely
- [x] Update `pyproject.toml`
- [x] Add `structlog` logging
- [x] Improve error handling (corrupted PDFs, Ollama down)
- [x] Enhance prompts with stricter guardrails
- [x] Add extraction quality validation
- [x] Document common issues in README

### Sprint 3: Enhancements (Completed)

#### 3.1 Hybrid Search Implementation

- [x] Add `rank-bm25` dependency to pyproject.toml
- [x] Create `app/search.py` module
- [x] Implement BM25 index building during ingestion
- [x] Save BM25 index to `index/bm25/{provider}_index.pkl`
- [x] Implement Reciprocal Rank Fusion (RRF) algorithm
- [x] Update `query.py` to use hybrid search
- [x] Add search mode parameter (vector/keyword/hybrid)
- [x] Add tests for hybrid ranking

#### 3.2 Definitions Auto-Linking

- [x] Create `app/definitions.py` module
- [x] Implement quoted term extraction from text
- [x] Build definitions index
- [x] Implement definition retrieval by term matching
- [x] Update prompt to include definitions section

#### 3.3 Output Formats

- [x] Create `app/output.py` module
- [x] Implement console output formatter using Rich
- [x] Implement JSON output formatter
- [x] Add `--format` flag to query command

</details>

______________________________________________________________________

## Future Phases (Post-OpenAI Migration)

The following items from v0.3 are deferred until the OpenAI migration is complete and validated:

### REST API (Sprint 4)

- FastAPI setup and endpoints
- Authentication and rate limiting
- OpenAPI documentation

### AWS Deployment (Sprint 5)

- Docker containerization
- EC2 deployment (simple single instance)
- Optional: Auto Scaling group for high availability
- CI/CD pipeline (GitHub Actions → EC2)

### Additional Data Providers

- OPRA, CTA/UTP document ingestion
- Cross-provider queries

______________________________________________________________________

## Cost Estimation (OpenAI)

### Per Query

| Operation             | Tokens  | Cost             |
| --------------------- | ------- | ---------------- |
| Embedding (query)     | ~50     | $0.00001         |
| Reranking (12 chunks) | ~24,000 | $0.024           |
| Answer generation     | ~5,000  | $0.005           |
| **Total**             |         | **~$0.03/query** |

### Monthly Estimates

| Usage  | Queries/day | Monthly Cost |
| ------ | ----------- | ------------ |
| Light  | 100         | ~$90         |
| Medium | 200         | ~$180        |
| Heavy  | 350         | ~$315        |

______________________________________________________________________

## Migration Checklist

Before switching from master to openai branch in production:

- [ ] All 10 phases complete
- [ ] Evaluation set passes (≥90% chunk recall)
- [ ] No false refusals on known-good queries
- [ ] Debug mode validated
- [ ] README updated with OpenAI setup
- [ ] Cost monitoring in place
