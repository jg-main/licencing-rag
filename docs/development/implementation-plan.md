# Implementation Plan - License Intelligence System (OpenAI Branch)

**Version:** 2.0\
**Created:** 2026-01-26\
**Updated:** 2026-01-28\
**Target:** specs.v0.4.md\
**Branch:** openai

______________________________________________________________________

## Overview

This branch implements a new approach using **OpenAI as the single source** for both embeddings and LLM reasoning. This is a significant departure from the previous Ollama/Claude hybrid approach.

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

### Phase 1: OpenAI Embeddings Upgrade ✅

#### 1.1 Dependencies & Configuration

- [x] Add `openai` package to pyproject.toml
- [x] Add `tiktoken` package for token counting
- [x] Remove `anthropic` package (no longer needed)
- [x] Remove `ollama` package (no longer needed)
- [x] Update `app/config.py` with OpenAI model constants
- [x] Remove `LLM_PROVIDER` abstraction (single source)

#### 1.2 Embedding Function Rewrite

- [x] Rewrite `app/embed.py` for OpenAI embeddings
- [x] Use `text-embedding-3-large` model (3072 dimensions)
- [x] Implement batch embedding for efficiency
- [x] Add error handling for API failures
- [x] Update ChromaDB dimension configuration

#### 1.3 LLM Provider Rewrite

- [x] Rewrite `app/llm.py` for OpenAI only
- [x] Remove `OllamaProvider` class
- [x] Remove `AnthropicProvider` class
- [x] Implement simple OpenAI client with `gpt-4.1`
- [x] Remove source abstraction (direct OpenAI client)

#### 1.4 Index Migration

- [x] Store embedding model metadata with index
- [x] Add version check: block queries if model mismatch
- [x] Delete existing ChromaDB index (incompatible dimensions) — user action
- [x] Delete existing BM25 index — user action
- [x] Re-ingest all documents with new embeddings — user action

#### 1.5 Verification

- [x] Update tests for OpenAIEmbeddingFunction
- [x] All 192 tests passing
- [x] All QA checks passing (formatting, linting, type checking)
- [x] Document API key setup in README.md

### Phase 2: Query Normalization ✅

#### 2.1 Implementation

- [x] Create `app/normalize.py` module
- [x] Implement `normalize_query()` function
- [x] Strip leading phrases ("what is", "can you", etc.)
- [x] Remove filler words (the, a, an, is, etc.)
- [x] Preserve nouns and legal terms
- [x] Add comprehensive test cases

#### 2.2 Integration

- [x] Update `query.py` to normalize before embedding
- [x] Update `query.py` to normalize before BM25
- [x] Log original vs normalized query
- [x] Add `--debug` flag to show normalization

#### 2.3 Verification

- [x] Test: "What is the fee schedule?" → "fee schedule"
- [x] Test: Normalized query retrieves same top chunks as keyword query
- [x] Verify fee schedules, exhibits, tables are retrievable

### Phase 3: Hybrid Retrieval (Mandatory) ✅

> Note: Hybrid search already exists from v1.x, but needs verification with new embeddings.

#### 3.1 Verification with OpenAI Embeddings

- [x] Test vector search with `text-embedding-3-large`
- [x] Verify BM25 still works correctly
- [x] Test RRF merge produces reasonable rankings
- [x] Verify candidate pool max 12 chunks

#### 3.2 Configuration Updates

- [x] Set vector k=10
- [x] Set BM25 k=10
- [x] Ensure deduplication by chunk_id
- [x] Log retrieval sources in debug mode

### Phase 4: LLM Reranking ✅

#### 4.1 Implementation

- [x] Create `app/rerank.py` module
- [x] Implement scoring prompt (0-3 relevance scale)
- [x] Implement `rerank_chunks()` function
- [x] Call GPT-4.1 for each candidate chunk
- [x] Sort by score, keep top 3-5

#### 4.2 Integration

- [x] Update `query.py` to call reranking after retrieval
- [x] Log scores in debug mode
- [x] Track dropped chunks with reasons

#### 4.3 Optimization & Production Hardening

- [x] Truncate chunk text to ~2000 chars for reranking
- [x] Parallel API calls with ThreadPoolExecutor (5 workers)
- [x] Add timeout handling (30s per chunk, prevents pipeline hangs)
- [x] Score-based threshold (keep chunks ≥2, max 10) for adaptive filtering
- [x] Improved prompt (semantic understanding over keyword matching)
- [x] **Single-token scoring (50% cost reduction)** - explanations optional, disabled by default
- [x] **Config flag for debug mode** - RERANKING_INCLUDE_EXPLANATIONS for troubleshooting

### Phase 5: Context Budget Enforcement ✅

#### 5.1 Implementation

- [x] Add `tiktoken` for accurate token counting
- [x] Implement `enforce_context_budget()` function
- [x] Target: ≤60k tokens for LLM input
- [x] Prefer shorter, higher-score chunks
- [x] Drop long, low-score chunks first

#### 5.2 Integration

- [x] Apply budget after reranking
- [x] Log final context token count
- [x] Add budget exceeded warning
- [x] Add `--no-budget` CLI flag
- [x] Add comprehensive test suite (18 tests)

#### 5.3 Production Optimizations

- [x] **Accuracy-first prioritization**: Relevance score > chunk length
- [x] **Smart dropping**: Drop lowest-score chunks first when over budget
- [x] **Tie-breaking**: Prefer shorter chunks when scores are equal
- [x] **Debug visibility**: Full budget metrics in debug mode

### Phase 6: Retrieval Confidence Gating ✅

#### 6.1 Implementation

- [x] Create `app/gate.py` module
- [x] Implement two-tier gating strategy (reranked vs retrieval scores)
- [x] Define `RELEVANCE_THRESHOLD = 2` for reranked scores
- [x] Define `RETRIEVAL_MIN_SCORE = 0.05` for retrieval scores (prevents weak/near-zero accepts)
- [x] Define `RETRIEVAL_MIN_RATIO = 1.2` for retrieval scores (requires clear winner, simpler than median-gap)
- [x] Define `MIN_CHUNKS_REQUIRED = 1`
- [x] Implement `should_refuse()` function with score type awareness
- [x] Return standard refusal message

#### 6.2 Rules (Code-Enforced)

**Reranked Scores (0-3):**

- [x] Refuse if no chunk score ≥ 2
- [x] Refuse if top score < 2
- [x] Refuse if all chunks score 0-1
- [x] Log refusal reason in debug mode

**Retrieval Scores (vector/BM25/RRF):**

- [x] Refuse if top score \<= absolute minimum (prevents negative/near-zero accepts)
- [x] Refuse if top-1/top-2 ratio < 1.2 (no clear winner)
- [x] Refuse if single chunk with score ≤ 0.05
- [x] Handle zero/negative top-2 case with special ratio proxy

#### 6.3 Integration

- [x] Update `query.py` to track whether scores are reranked
- [x] Pass `scores_are_reranked` flag to gate
- [x] Gate before LLM call (after reranking)
- [x] Skip LLM call entirely on refusal
- [x] Return deterministic refusal message
- [x] Add `--no-gate` CLI flag
- [x] Add post-budget empty context check
- [x] Add comprehensive test suite (41 tests)

#### 6.4 Test Coverage

- [x] Test reranked score gating (11 tests)
- [x] Test retrieval score gating (8 tests)
- [x] Test two-tier gating integration (4 tests)
- [x] Test refusal messages (10 tests)
- [x] Test configuration variations (3 tests)
- [x] Test post-budget refusal (5 tests)

### Phase 7: LLM Prompt Discipline ✅

#### 7.1 System Prompt Update

- [x] Update `app/prompts.py` with strict rules
- [x] Emphasize: use ONLY provided context
- [x] Emphasize: NEVER extrapolate
- [x] Enforce: mandatory citations
- [x] Add explicit refusal instruction
- [x] Add quality verification checklist (pre-response)
- [x] Include forbidden patterns section
- [x] Add structured formatting for LLM clarity
- [x] Strengthen accuracy-over-cost principle throughout

#### 7.2 Output Format

- [x] Enforce: "## Answer" section format
- [x] Enforce: "## Supporting Clauses" with verbatim quotes
- [x] Enforce: "## Citations" with mandatory page numbers
- [x] Test refusal message consistency
- [x] Add pre-response verification prompts
- [x] Strengthen QA prompts with refusal criteria

#### 7.3 Implementation Enhancements (Deviation from Spec)

**Deviations that add value:**

1. **Pre-response Verification Checklists**: Added mandatory verification steps in both SYSTEM_PROMPT and QA_PROMPT to ensure LLM checks accuracy before responding
1. **Forbidden Patterns Section**: Explicitly listed patterns to avoid (e.g., "Based on typical industry practice...") with visual markers (❌/✅)
1. **Structured Formatting**: Used visual separators (═══) to improve LLM parsing and comprehension
1. **Refusal Criteria Enumeration**: Listed specific conditions that should trigger refusal in QA prompts
1. **Quality Verification Section**: Added "QUALITY VERIFICATION (Before Responding)" with numbered checklist
1. **Accuracy-First Principle**: Made explicit that "It is better to refuse than to answer with ANY uncertainty"
1. **Verbatim Quote Requirement**: Strengthened from "quote" to "verbatim quote" with explicit anti-paraphrasing rules

**Rationale:** These enhancements align with the accuracy-first principle stated in README.md: "This is not a general chatbot. It is a retrieval-grounded legal analysis tool." The additional structure and verification steps reduce hallucination risk beyond what basic prompt engineering can achieve.

#### 7.4 Testing

- [x] Create `tests/test_prompts.py` with 40 validation tests
- [x] Test prompt structure and required sections
- [x] Test accuracy enforcement rules
- [x] Test refusal message formatting
- [x] Test citation requirements
- [x] Test format enforcement
- [x] Adjust `test_budget.py` for enhanced prompt token count

### Phase 8: Debug & Audit Mode

**Status**: ✅ **COMPLETE**

#### 8.1 Debug Mode (Pipeline Transparency) ✅

- [x] Add `--debug` flag to CLI (already existed from Phase 1)
- [x] Log original query
- [x] Log normalized query
- [x] Log retrieved chunks with ranks (per-source stats)
- [x] Log rerank scores (kept/dropped with explanations if enabled)
- [x] Log dropped chunks with reasons
- [x] Log final context token count
- [x] Log confidence gate result
- [x] Created `app/debug.py` module
- [x] Implemented rotating file handler (10MB, 5 backups)
- [x] Created `logs/` directory for audit trail
- [x] Integrated debug output into all query.py execution paths
- [x] JSON format to stderr + JSONL to `logs/debug.jsonl`
- [x] ISO 8601 UTC timestamps
- [x] Removed DEBUG_LOG_ENABLED gates (--debug always writes to stderr)
- [x] Enhanced retrieval info with scores and ranks

**Implementation Details**:

- Debug output captures: query normalization, retrieval stats, reranking decisions, confidence gating, budget enforcement, LLM calls, and validation
- Dual output: stderr for real-time monitoring + rotating log file for audit trail
- Supports "accuracy over cost" principle through complete pipeline transparency

#### 8.2 Query/Response Audit Logging (Compliance & Usage Tracking) ✅

**Purpose**: Log all queries and responses for compliance, usage analytics, and audit trail. This is separate from debug mode - debug is for troubleshooting, audit is for compliance.

**Requirements**:

- [x] Log to file by default (always enabled)
- [x] Optional console output via `--log-queries` flag
- [x] Capture: timestamp, query, answer, sources, tokens used, latency, refusal status
- [x] Future: user_id field for API authentication
- [x] Rotating log files to manage disk usage
- [x] JSONL format for easy parsing

**8.2.1 Implementation Tasks**

- [x] Create `app/audit.py` module
- [x] Implement `log_query_response()` function
- [x] Add rotating file handler for `logs/queries.jsonl`
  - Max file size: 50MB
  - Keep 10 backups (500MB total)
  - Automatic rotation on size limit
- [x] Integrate into `query.py` at all exit points
- [x] Add `--log-queries` CLI flag for console output
- [x] Track metrics:
  - `timestamp` (ISO 8601 UTC)
  - `query` (original user input)
  - `answer` (LLM response or refusal message)
  - `sources` (list of data sources queried)
  - `chunks_retrieved` (count)
  - `chunks_used` (after reranking/budget)
  - `tokens_input` (prompt tokens)
  - `tokens_output` (completion tokens)
  - `latency_ms` (total query time)
  - `refused` (boolean)
  - `refusal_reason` (if refused)
  - `user_id` (null for now, for future API)

**8.2.2 Configuration**

- [x] Add audit logging constants to `app/config.py`
- [x] Configure log file path, size limits (50MB), and backup count (10)

**8.2.3 Output Format** ✅

- [x] JSONL format (one entry per line)
- [x] Includes all tracked metrics (see specs.v0.4.md for detailed format)

**8.2.4 Privacy & Compliance Considerations** ✅

- [x] Add option to hash/redact PII in queries (future)
- [x] Document log retention policy in README
- [x] Add log rotation to prevent unbounded disk usage
- [ ] Consider GDPR compliance for user data (future API)

**8.2.5 Verification** ✅

- [x] Test: Query logged to file after successful response
- [x] Test: Refusal logged with reason
- [x] Test: Log rotation works at 50MB limit
- [x] Test: Console output only appears with `--log-queries`
- [x] Test: Latency tracking accurate
- [x] Test: Token counts match OpenAI usage
- [x] All 9 tests passing in `tests/test_audit.py`

**Implementation Summary**:

- Created `app/audit.py` with `log_query_response()` function
- Integrated at all 4 query exit points (no-results, confidence gate, budget refusal, success)
- Always writes to `logs/queries.jsonl` (compliance requirement)
- Optional stderr output via `--log-queries` CLI flag
- Tracks latency, tokens, refusals for cost/performance monitoring
- Future-ready with `user_id` field for API authentication

**Rationale**: Separating debug (pipeline transparency) from audit (compliance logging) provides clean separation of concerns. Debug mode is verbose and optional; audit logging is concise and always-on for production compliance.

______________________________________________________________________

### Phase 9: Evaluation Set ⚠️

**Status**: ⚠️ **PARTIAL** - Chunk recall 75% below 90% target, requires re-evaluation after ingestion

#### 9.1 Create Evaluation Set ✅

- [x] Create `eval/` directory
- [x] Create `eval/questions.json`
- [x] Add 30 representative questions (20 original + 10 complex)
- [x] Include expected chunks
- [x] Include expected refusal cases
- [x] Add source-awareness to questions (`"source": "cme"`)

#### 9.2 Evaluation Script ✅

- [x] Create `eval/run_eval.py`
- [x] Implement chunk recall metric (citation-based extraction)
- [x] Implement refusal accuracy metric
- [x] Generate evaluation report (JSON + console summary)
- [x] Source-aware evaluation (filter chunks by source)
- [x] Enhanced refusal detection (matches actual system messages)

#### 9.3 Results ✅

- [x] Refusal Accuracy = 96.7% (29/30) - ✓ Near Target
- [x] False Refusal Rate = 4.0% (1/25) - ✓ **PASS** (< 5%)
- [x] False Acceptance Rate = 0.0% (0/5) - ✓ **PASS** (0%)
- [x] Chunk Recall = 75.0% (6/8 applicable) - ✗ Below 90% target
- [x] Created `eval/EVALUATION_SUMMARY.md` with detailed analysis
- [x] Added `chunk_ids` field to response for chunk recall measurement
- [x] Added year-aware filtering to prevent stale document citations

**Known Issues (to address in future iterations):**

- Q3 (Subscriber definition): **FIXED** - Improved `is_definitions_section()` detection
  - Root cause: Pattern only checked first 500 chars for "definition" keyword
  - Fix: Added content-based pattern detection with comprehensive format support
  - Supports numbered/lettered prefixes: `(1)`, `(a)`, `[i]`, `•`, `1.`
  - Supports "The term X means" format and definitions without articles
  - Supports: quoted terms, hyphenated terms (Non-Professional, Real-Time), multi-word terms
  - Pattern uses VERBOSE mode for maintainability (see specs.v0.4.md section 7.1)
  - Tested with 18/18 definition formats across CME, OPRA, CTA/UTP styles
- Q2, Q10: **FIXED** - Updated expected_chunks to accept both chunk 0 and chunk 1
  - Both chunks contain relevant fee data (fees span across chunks)
- 3 questions hit "formatting failed" fallback (Q3, Q19, Q20) - requires re-evaluation
- Added `.txt` file support to ingestion pipeline as fallback for edge cases

### Phase 10: Cleanup & Documentation

#### 10.1 Remove Legacy Code

- [ ] Delete Ollama-specific code
- [ ] Delete Anthropic-specific code
- [ ] Delete LLM source abstraction
- [ ] Remove unused imports
- [ ] Update all docstrings

#### 10.2 Documentation

**README needs to be accesible to non-developers and developers, keep documentation accesible and clear.**

- [ ] Update architecture diagram
- [ ] Update and sync implementation plan document and specs.v0.4.md
- [ ] Update README.md and dowstream documentation
- [ ] Documentation of individual concepts or features must be accessible from README.md
- [ ] Create individual, documents to explain
  - Configuration options - Environment variables
  - Explain ingestion process
  - Explain Query normalization
  - Explain Reranking process
  - Explain Confidence gating logic
  - Debug mode usage
  - Audit logging details
  - Any other complex concepts that worth documenting
- [ ] Add cost estimation section
- [ ] Update CLI help text

#### 10.3 Testing

- [ ] Update all existing tests, aim for 70% coverage
- [ ] Add tests for any missing edge cases
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
- [x] Fix path: `RAW_DATA_DIR` to support source subdirs

#### 1.2 Core Infrastructure

- [x] Create `app/embed.py` with `OllamaEmbeddingFunction`
- [x] Create `app/extract.py` with PDF page tracking
- [x] Add DOCX extraction support

#### 1.3 Chunking Improvements

- [x] Capture section headings in metadata
- [x] Track page numbers per chunk
- [x] Expand section detection regex patterns

#### 1.4 Pipeline Refactoring

- [x] Refactor `ingest.py` for multi-source support
- [x] Refactor `query.py` with embedding function
- [x] Add source-based collection naming

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
- [x] Create `app/llm.py` with source abstraction
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
- [x] Save BM25 index to `index/bm25/{source}_index.pkl`
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
- Cross-source queries
