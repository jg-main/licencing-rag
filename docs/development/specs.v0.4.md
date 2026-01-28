# CME License Intelligence System - Technical Product Brief

**Project Name:** License Intelligence System (OpenAI RAG)  
**Version:** 0.4  
**Last Updated:** 2026-01-28  
**Branch:** openai

---

## Changelog from v0.3

- **BREAKING**: Switched to OpenAI as single provider for both embeddings and LLM
- **BREAKING**: Removed Ollama/Claude support (single-provider architecture)
- **Added**: Query normalization (pre-retrieval processing)
- **Added**: LLM-based reranking with GPT-4.1
- **Added**: Context budget enforcement (≤60k tokens)
- **Added**: Retrieval confidence gating (code-enforced refusal)
- **Added**: Debug/audit mode for transparency
- **Added**: Evaluation set for clause retrieval accuracy
- **Removed**: Multi-LLM provider abstraction (Ollama, Anthropic)
- **Removed**: Local embedding model support
- **Updated**: Refusal is now enforced in code, not just prompts

---

## 1. Objective

Build a **high-precision, clause-level Retrieval-Augmented Generation (RAG) system** for CME licensing documents that:

- Answers **natural-language licensing questions**
- Retrieves the **exact contractual clauses**
- **Refuses deterministically** when documents are silent (code-enforced)
- Produces **auditable citations**
- Minimizes hallucinations and irrelevant context
- Is deployable behind an API (FastAPI) and callable from Slack

This is **not** a general chatbot. It is a **retrieval-grounded legal analysis tool**.

### Core Principle

> **Retrieval quality > LLM cleverness**  
> The LLM is not a knowledge source—it is only the renderer.

---

## 2. Model Stack (Single Provider: OpenAI)

### Embeddings

| Purpose | Provider | Model | Dimensions |
|---------|----------|-------|------------|
| Document chunks | OpenAI | `text-embedding-3-large` | 3072 |
| Query embedding | OpenAI | `text-embedding-3-large` | 3072 |

### LLM Reasoning

| Purpose | Provider | Model | Notes |
|---------|----------|-------|-------|
| Answer generation | OpenAI | `gpt-4.1` | Clause-grounded responses |
| Reranking | OpenAI | `gpt-4.1` | Relevance scoring (0-3) |

> ⚠️ **Any change to these models is a breaking change and requires explicit review.**

### Configuration

```bash
export OPENAI_API_KEY="sk-..."
```

No fallback providers. OpenAI is the single source for all model operations.

---

## 3. Non-Negotiable Design Principles

1. **Retrieval quality > LLM cleverness** — Focus on getting the right chunks
2. **The LLM is not a knowledge source** — Never rely on model knowledge
3. **Refusal is enforced in code, not only via prompt** — Deterministic gating
4. **Context trimming is mandatory** — Quality + cost control
5. **All answers must be traceable to documents** — Full citation chain
6. **Single provider only (OpenAI)** — No provider abstraction complexity

---

## 4. Non-Goals (Explicitly Out of Scope)

- Conversation memory
- Increasing chunk size for better recall
- Prompt-only fixes for retrieval
- Using the LLM to infer missing terms
- External browsing or general legal knowledge
- Multi-provider support (Ollama, Claude, etc.)
- OCR for image-based PDFs
- Automated clause negotiation or contract generation

---

## 5. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Document Ingestion Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│  data/raw/{provider}/**/*.pdf                                   │
│         ↓                                                        │
│     Extract (PyMuPDF)                                           │
│         ↓                                                        │
│     Chunk (section-aware)                                       │
│         ↓                                                        │
│     Embed (OpenAI text-embedding-3-large)                       │
│         ↓                                                        │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  ChromaDB       │    │  BM25 Index     │                     │
│  │  (vectors)      │    │  (keywords)     │                     │
│  └─────────────────┘    └─────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         Query Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│  User Question                                                   │
│         ↓                                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Query Normalization (NEW)                               │    │
│  │  - Lowercase                                             │    │
│  │  - Strip phrases: "what is", "can you", "how does"       │    │
│  │  - Remove filler words                                   │    │
│  │  - Preserve nouns and legal terms                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│         ↓                                                        │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  Vector Search  │    │  BM25 Search    │                     │
│  │  (k=10)         │    │  (k=10)         │                     │
│  └────────┬────────┘    └────────┬────────┘                     │
│           └──────────┬───────────┘                               │
│                      ↓                                           │
│         Merge (dedupe by chunk_id)                              │
│         Candidate pool: max 12 chunks                           │
│                      ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Reranking (NEW)                                         │    │
│  │  GPT-4.1 scores each chunk 0-3                           │    │
│  │  Keep top 3-5 chunks                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                      ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Confidence Gating (NEW)                                 │    │
│  │  If no chunk ≥ threshold → REFUSE                        │    │
│  │  If top score < confidence → REFUSE                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                      ↓                                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Context Budget Enforcement (NEW)                        │    │
│  │  Target: ≤60k tokens                                     │    │
│  │  Drop low-score, long chunks first                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                      ↓                                           │
│         LLM Prompt (GPT-4.1)                                    │
│                      ↓                                           │
│         Answer + Citations                                       │
│                      ↓                                           │
│         Debug Log (if enabled)                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Technology Stack

### Runtime

- Python 3.13+
- Local execution / Docker / AWS ECS (Fargate)

### Models (OpenAI Only)

| Purpose | Model | Notes |
|---------|-------|-------|
| Embeddings | `text-embedding-3-large` | 3072 dimensions |
| LLM | `gpt-4.1` | Answer generation + reranking |

### Libraries

| Library | Purpose | Version |
|---------|---------|---------|
| `openai` | OpenAI API client | 1.0+ |
| `chromadb` | Vector database | 1.4+ |
| `rank-bm25` | BM25 keyword search | 0.2+ |
| `tiktoken` | Token counting | 0.9+ |
| `pymupdf` | PDF extraction | 1.26+ |
| `python-docx` | DOCX extraction | 1.2+ |
| `fastapi` | REST API | 0.115+ |
| `uvicorn` | ASGI server | 0.32+ |
| `rich` | Console output | 14.0+ |
| `structlog` | Structured logging | 25.0+ |
| `pytest` | Testing | 8.0+ |

---

## 7. Directory Structure

```
licencing-rag/
├── app/
│   ├── __init__.py
│   ├── config.py           # Configuration (OpenAI models, thresholds)
│   ├── extract.py          # PDF/DOCX text extraction
│   ├── chunking.py         # Document chunking
│   ├── embed.py            # OpenAI embeddings (REWRITTEN)
│   ├── ingest.py           # Ingestion pipeline
│   ├── normalize.py        # Query normalization (NEW)
│   ├── search.py           # Hybrid search (vector + BM25)
│   ├── rerank.py           # GPT-4.1 reranking (NEW)
│   ├── gate.py             # Confidence gating (NEW)
│   ├── query.py            # Query pipeline (UPDATED)
│   ├── prompts.py          # LLM prompts (UPDATED)
│   ├── output.py           # Output formatting
│   └── logging.py          # Structured logging
├── data/
│   ├── raw/{provider}/     # Source documents
│   ├── text/{provider}/    # Extracted text
│   └── chunks/{provider}/  # Serialized chunks
├── index/
│   ├── chroma/             # ChromaDB vectors
│   └── bm25/               # BM25 keyword index
├── eval/
│   └── questions.json      # Evaluation set (NEW)
├── logs/
│   └── queries.jsonl       # Query audit log
├── api/
│   ├── __init__.py
│   ├── main.py             # FastAPI application
│   └── routes.py           # API endpoints
├── docs/
│   └── development/
│       ├── specs.v0.4.md   # This document
│       └── implementation-plan.md
├── pyproject.toml
└── README.md
```

---

## 8. Query Normalization (Phase 2)

### Objective

Ensure conversational questions behave like keyword queries.

### Implementation

```python
# app/normalize.py

STRIP_PREFIXES = [
    "what is", "what are", "what's",
    "can you", "could you", "would you",
    "please explain", "please tell me",
    "how does", "how do", "how is",
    "tell me about", "explain",
]

FILLER_WORDS = {
    "the", "a", "an", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall",
    "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your",
}

def normalize_query(query: str) -> str:
    """Normalize query for better retrieval.
    
    1. Lowercase
    2. Strip leading phrases
    3. Remove filler words
    4. Preserve nouns and legal terms
    """
    text = query.lower().strip()
    
    # Strip prefix phrases
    for prefix in STRIP_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    
    # Remove filler words
    words = text.split()
    filtered = [w for w in words if w not in FILLER_WORDS]
    
    return " ".join(filtered)
```

### Example

| Original | Normalized |
|----------|------------|
| "What is the fee schedule for CME data?" | "fee schedule cme data" |
| "Can you explain redistribution requirements?" | "redistribution requirements" |
| "How does CME charge for real-time data?" | "cme charge real-time data" |

### Usage

The normalized query is used for:
- Vector embedding (OpenAI)
- BM25 keyword search

---

## 9. Hybrid Retrieval (Phase 3)

### Strategy

For each query:

1. **Vector search** — `text-embedding-3-large`, k=10
2. **Keyword/BM25 search** — section_heading + chunk text, k=10
3. **Merge** — Deduplicate by chunk_id
4. **Candidate pool** — Maximum 12 chunks

### Retrieval Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Vector k | 10 | Initial vector retrieval |
| BM25 k | 10 | Initial keyword retrieval |
| Candidate max | 12 | Before reranking |
| Final top | 3-5 | After reranking |

---

## 10. Reranking (Phase 4)

### Objective

Remove irrelevant chunks before the LLM sees them.

### Implementation

```python
# app/rerank.py

RERANK_PROMPT = """Score this chunk from 0-3 for relevance to the question.

Question: {question}

Chunk:
{chunk_text}

Scoring guide:
- 0: Not relevant at all
- 1: Tangentially related
- 2: Relevant but not directly answering
- 3: Directly relevant, contains answer

Output only the numeric score (0, 1, 2, or 3):"""

async def rerank_chunks(
    question: str,
    chunks: list[dict],
    client: OpenAI,
) -> list[tuple[dict, int]]:
    """Score and rank chunks using GPT-4.1."""
    scored = []
    for chunk in chunks:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "user", "content": RERANK_PROMPT.format(
                    question=question,
                    chunk_text=chunk["text"][:2000],  # Limit for cost
                )}
            ],
            max_tokens=5,
            temperature=0,
        )
        score = int(response.choices[0].message.content.strip())
        scored.append((chunk, score))
    
    # Sort by score descending, keep top 3-5
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:5]
```

### Rules

- Score all candidate chunks (up to 12)
- Keep only top 3-5 chunks
- Discard all others

---

## 11. Confidence Gating (Phase 6)

### Objective

Refuse when evidence is weak or missing.

### Rules (Enforced in Code)

| Condition | Action |
|-----------|--------|
| No chunk score ≥ 2 | REFUSE |
| Top score < 2 | REFUSE |
| All chunks score 0-1 | REFUSE |

### Implementation

```python
# app/gate.py

RELEVANCE_THRESHOLD = 2  # Minimum score to consider relevant
CONFIDENCE_THRESHOLD = 2  # Minimum top score to proceed

def should_refuse(scored_chunks: list[tuple[dict, int]]) -> bool:
    """Determine if query should be refused based on retrieval confidence."""
    if not scored_chunks:
        return True
    
    top_score = scored_chunks[0][1]
    
    # Refuse if top score below threshold
    if top_score < CONFIDENCE_THRESHOLD:
        return True
    
    # Refuse if no chunk meets relevance threshold
    if not any(score >= RELEVANCE_THRESHOLD for _, score in scored_chunks):
        return True
    
    return False

REFUSAL_MESSAGE = "This is not addressed in the provided CME documents."
```

---

## 12. Context Budget Enforcement (Phase 5)

### Objective

Reduce cost and hallucination risk.

### Targets

| Metric | Before | After |
|--------|--------|-------|
| Avg LLM input | ~100k tokens | ≤60k tokens |

### Rules

- Hard cap on number of chunks (3-5)
- Prefer shorter clauses with higher relevance scores
- Drop long, low-score chunks first
- Use `tiktoken` for accurate token counting

### Implementation

```python
# app/query.py

import tiktoken

MAX_CONTEXT_TOKENS = 60000
ENCODING = tiktoken.encoding_for_model("gpt-4.1")

def enforce_context_budget(
    chunks: list[tuple[dict, int]],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> list[dict]:
    """Trim context to fit within token budget."""
    selected = []
    total_tokens = 0
    
    for chunk, score in chunks:
        chunk_tokens = len(ENCODING.encode(chunk["text"]))
        if total_tokens + chunk_tokens <= max_tokens:
            selected.append(chunk)
            total_tokens += chunk_tokens
        else:
            break  # Already sorted by score, stop here
    
    return selected
```

---

## 13. LLM Prompt Discipline (Phase 7)

### System Prompt

```
You are a legal document analyst. You answer questions using ONLY the 
provided context from CME licensing documents.

STRICT RULES:
1. Use ONLY information from the provided context
2. NEVER use prior knowledge or general legal principles
3. NEVER speculate or extrapolate beyond the documents
4. If the answer is not in the context, respond with the exact phrase:
   "This is not addressed in the provided CME documents."
5. Always cite the specific document, section, and page

OUTPUT FORMAT:
Answer: <concise, clause-grounded answer>

Citations:
- <Document> | <Section> | Page <X>
```

### User Prompt Template

```
Context:
{context}

Question: {question}
```

---

## 14. Debug & Audit Mode (Phase 8)

### Debug Flag

```bash
rag query "fee schedule" --debug
```

### Debug Output

```json
{
  "original_query": "What is the fee schedule?",
  "normalized_query": "fee schedule",
  "retrieved_chunks": [
    {"chunk_id": "cme_fees_schedule.pdf_0", "bm25_rank": 1, "vector_rank": 3},
    {"chunk_id": "cme_fees_schedule.pdf_1", "bm25_rank": 2, "vector_rank": 1}
  ],
  "rerank_scores": [
    {"chunk_id": "cme_fees_schedule.pdf_0", "score": 3},
    {"chunk_id": "cme_fees_schedule.pdf_1", "score": 2}
  ],
  "dropped_chunks": [
    {"chunk_id": "cme_general_terms.pdf_5", "score": 0, "reason": "below_threshold"}
  ],
  "final_context_tokens": 4523,
  "confidence_gate": "PASS",
  "answer_generated": true
}
```

---

## 15. Evaluation Set (Phase 9)

### File: `eval/questions.json`

```json
{
  "version": "1.0",
  "questions": [
    {
      "id": "q001",
      "question": "What is the real-time data fee for CME?",
      "expected_chunks": ["cme_fees__january-2026-market-data-fee-list.pdf_0"],
      "expected_terms": ["$134.50", "Device"],
      "should_refuse": false
    },
    {
      "id": "q002",
      "question": "What is the definition of a Subscriber?",
      "expected_chunks": ["cme_legal__schedule-2-to-the-ila.pdf_definitions"],
      "expected_terms": ["Subscriber"],
      "should_refuse": false
    },
    {
      "id": "q003",
      "question": "What is Bitcoin?",
      "expected_chunks": [],
      "expected_terms": [],
      "should_refuse": true
    }
  ]
}
```

### Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Chunk Recall | Expected chunks retrieved | ≥90% |
| Refusal Accuracy | Correct refusals | 100% |
| False Refusal Rate | Incorrect refusals | <5% |

---

## 16. Output Format

### Console Output (Rich)

```
╭──────────────────── RESPONSE (Sources: CME) ────────────────────╮
│                                                                  │
│  Answer                                                          │
│                                                                  │
│  The real-time data fee for CME is $134.50 per device per month. │
│                                                                  │
│  Citations                                                       │
│  • january-2026-market-data-fee-list.pdf | Page 1                │
│                                                                  │
╰──────────────────────────────────────────────────────────────────╯
```

### JSON Output

```json
{
  "answer": "The real-time data fee...",
  "citations": [
    {"document": "january-2026-market-data-fee-list.pdf", "page": 1}
  ],
  "metadata": {
    "query_id": "uuid",
    "context_tokens": 4523,
    "model": "gpt-4.1"
  }
}
```

---

## 17. Cost Estimation

### Per Query

| Operation | Tokens | Cost |
|-----------|--------|------|
| Embedding (query) | ~50 | $0.00001 |
| Reranking (12 chunks) | ~24,000 | $0.024 |
| Answer generation | ~5,000 | $0.005 |
| **Total** | | **~$0.03/query** |

### Monthly (100 queries/day)

| Usage | Queries | Cost |
|-------|---------|------|
| Light | 3,000 | ~$90 |
| Medium | 6,000 | ~$180 |
| Heavy | 10,000 | ~$300 |

---

## 18. Migration from v0.3

### Breaking Changes

1. **Re-embed all documents** — Ollama embeddings incompatible with OpenAI
2. **Delete existing ChromaDB index** — Different dimensions (768 → 3072)
3. **Remove Ollama/Claude config** — Single provider only
4. **Update environment variables** — `OPENAI_API_KEY` required

### Migration Steps

```bash
# 1. Set OpenAI API key
export OPENAI_API_KEY="sk-..."

# 2. Delete old indexes
rm -rf index/chroma index/bm25

# 3. Re-ingest all documents
rag ingest --provider cme --force

# 4. Verify with test query
rag query "fee schedule" --debug
```

---

## 19. Expected Outcomes

After implementation:

- ✅ Conversational queries map to correct clauses
- ✅ Irrelevant context is eliminated (reranking)
- ✅ Refusals are reliable and boring (code-enforced)
- ✅ Input token usage drops materially (≤60k)
- ✅ Cost per query is predictable (~$0.03)
- ✅ Answers are auditable and defensible (debug mode)
- ✅ Evaluation set validates retrieval accuracy
