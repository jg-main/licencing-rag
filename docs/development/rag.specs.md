# CME License Intelligence System - Technical Product Brief

**Project Name:** License Intelligence System (OpenAI RAG)\
**Version:** 0.4\
**Last Updated:** 2026-01-30\
**Branch:** openai

______________________________________________________________________

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

> **Retrieval quality > LLM cleverness**\
> The LLM is not a knowledge source—it is only the renderer.

______________________________________________________________________

## 2. Model Stack (Single Provider: OpenAI)

### Embeddings

| Purpose         | Provider | Model                    | Dimensions |
| --------------- | -------- | ------------------------ | ---------- |
| Document chunks | OpenAI   | `text-embedding-3-large` | 3072       |
| Query embedding | OpenAI   | `text-embedding-3-large` | 3072       |

### LLM Reasoning

| Purpose           | Provider | Model     | Notes                     |
| ----------------- | -------- | --------- | ------------------------- |
| Answer generation | OpenAI   | `gpt-4.1` | Clause-grounded responses |
| Reranking         | OpenAI   | `gpt-4.1` | Relevance scoring (0-3)   |

> ⚠️ **Any change to these models is a breaking change and requires explicit review.**

### Configuration

```bash
export OPENAI_API_KEY="sk-..."
```

No fallback sources. OpenAI is the single source for all model operations.

______________________________________________________________________

## 3. Non-Negotiable Design Principles

1. **Retrieval quality > LLM cleverness** — Focus on getting the right chunks
1. **The LLM is not a knowledge source** — Never rely on model knowledge
1. **Refusal is enforced in code, not only via prompt** — Deterministic gating
1. **Context trimming is mandatory** — Quality + cost control
1. **All answers must be traceable to documents** — Full citation chain
1. **Single source only (OpenAI)** — No source abstraction complexity

______________________________________________________________________

## 4. Non-Goals (Explicitly Out of Scope)

- Conversation memory
- Increasing chunk size for better recall
- Prompt-only fixes for retrieval
- Using the LLM to infer missing terms
- External browsing or general legal knowledge
- Multi-source support (Ollama, Claude, etc.)
- OCR for image-based PDFs
- Automated clause negotiation or contract generation

______________________________________________________________________

## 5. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Document Ingestion Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│  data/raw/{source}/**/*.{pdf,docx,txt}                          │
│         ↓                                                        │
│     Extract (PyMuPDF/python-docx/plain-text)                    │
│         ↓                                                        │
│     Chunk (section-aware + definitions detection)               │
│         ↓                                                        │
│     Embed (OpenAI text-embedding-3-large)                       │
│         ↓                                                        │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │  ChromaDB       │    │  BM25 Index     │    │  Definitions │ │
│  │  (vectors)      │    │  (keywords)     │    │  Index       │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
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

______________________________________________________________________

## 6. Technology Stack

### Runtime

- Python 3.13+
- Local execution / Docker
- AWS EC2 (simple) with optional Auto Scaling

### Models (OpenAI Only)

| Purpose    | Model                    | Notes                         |
| ---------- | ------------------------ | ----------------------------- |
| Embeddings | `text-embedding-3-large` | 3072 dimensions               |
| LLM        | `gpt-4.1`                | Answer generation + reranking |

### Libraries

| Library       | Purpose             | Version |
| ------------- | ------------------- | ------- |
| `openai`      | OpenAI API client   | 1.0+    |
| `chromadb`    | Vector database     | 1.4+    |
| `rank-bm25`   | BM25 keyword search | 0.2+    |
| `tiktoken`    | Token counting      | 0.9+    |
| `pymupdf`     | PDF extraction      | 1.26+   |
| `python-docx` | DOCX extraction     | 1.2+    |
| `fastapi`     | REST API            | 0.115+  |
| `uvicorn`     | ASGI server         | 0.32+   |
| `rich`        | Console output      | 14.0+   |
| `structlog`   | Structured logging  | 25.0+   |
| `pytest`      | Testing             | 8.0+    |

______________________________________________________________________

## 7. Directory Structure

```
licencing-rag/
├── app/
│   ├── __init__.py
│   ├── config.py           # Configuration (OpenAI models, thresholds)
│   ├── extract.py          # PDF/DOCX/TXT text extraction
│   ├── chunking.py         # Document chunking with definitions detection
│   ├── definitions.py      # Definitions index and term extraction
│   ├── embed.py            # OpenAI embeddings (REWRITTEN)
│   ├── ingest.py           # Ingestion pipeline
│   ├── normalize.py        # Query normalization (NEW)
│   ├── search.py           # Hybrid search (vector + BM25)
│   ├── rerank.py           # GPT-4.1 reranking (NEW)
│   ├── gate.py             # Confidence gating (NEW)
│   ├── budget.py           # Context budget enforcement
│   ├── query.py            # Query pipeline (UPDATED)
│   ├── prompts.py          # LLM prompts (UPDATED)
│   ├── validate.py         # Output validation
│   ├── output.py           # Output formatting
│   ├── audit.py            # Query/response audit logging
│   ├── debug.py            # Debug output module
│   └── logging.py          # Structured logging
├── data/
│   ├── raw/{source}/     # Source documents
│   ├── text/{source}/    # Extracted text
│   └── chunks/{source}/  # Serialized chunks
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
│       ├── rag.specs.md   # This document
│       └── rag.implementation-plan.md
├── pyproject.toml
└── README.md
```

______________________________________________________________________

## 7.1 Definitions Section Detection

### Objective

Automatically identify chunks containing defined terms so they can be indexed for auto-linking and prioritized in retrieval for definition-related queries.

### Detection Strategy

Chunks are marked as `is_definitions: true` if either condition is met:

1. **Explicit markers**: The word "definition" or "defined term" appears in the first 500 characters of the chunk
1. **Content patterns**: Two or more lines match the definition pattern

### Content Pattern

```python
# Smart quote Unicode code points for PDF-extracted text
_LEFT_DOUBLE_QUOTE = "\u201c"   # "
_RIGHT_DOUBLE_QUOTE = "\u201d"  # "
_LEFT_SINGLE_QUOTE = "\u2018"   # '
_RIGHT_SINGLE_QUOTE = "\u2019"  # '
_QUOTE_CLASS = f'["\'{_LEFT_DOUBLE_QUOTE}{_RIGHT_DOUBLE_QUOTE}{_LEFT_SINGLE_QUOTE}{_RIGHT_SINGLE_QUOTE}]'

# Pattern to detect definition-style content
# Supports: quoted terms (straight + smart quotes), hyphenated terms, multi-word terms
# Handles: numbered/lettered prefixes (1), (a), [i], bullets, "The term"/"THE TERM" prefix
# Case-insensitive for means/shall mean; terms can start with digit or capital letter
# NOTE: Use literal space ' ' in term class, NOT \s (which matches newlines)
_DEFINITION_CONTENT_PATTERN = re.compile(
    rf"""
    (?:^|[\n])\s*                         # Start of line + optional leading whitespace
    (?:                                   # Optional list prefix group
        \(\s*[a-zA-Z0-9]+\s*\)            # (1), (a), (A), (i), etc.
        |
        \[\s*[a-zA-Z0-9]+\s*\]            # [1], [a], [A], etc.
        |
        [•\-\*]                           # Bullet points
        |
        \d+\.                             # 1., 2., etc.
    )?\s*
    (?:[Tt][Hh][Ee]\s+[Tt][Ee][Rr][Mm]\s+)?  # Optional: 'The term' / 'THE TERM'
    {_QUOTE_CLASS}?                       # Optional opening quote (straight + smart)
    [A-Z0-9][A-Za-z0-9\- &/.]*            # Term: caps OR digit start (space, not \s!)
    {_QUOTE_CLASS}?                       # Optional closing quote (straight + smart)
    \s*(?::|[Mm][Ee][Aa][Nn][Ss]|[Ss][Hh][Aa][Ll][Ll]\s+[Mm][Ee][Aa][Nn])
    \s+
    (?:[a-zA-Z]+)                         # First word of definition
    """,
    re.MULTILINE | re.VERBOSE,
)
```

### Supported Formats

| Format              | Example                                | Source          |
| ------------------- | -------------------------------------- | --------------- |
| Colon               | `Subscriber: any party...`             | CME Schedule 5  |
| Quoted means        | `"Subscriber" means any...`            | Legal contracts |
| Shall mean          | `Term shall mean...`                   | CTA/UTP         |
| Hyphenated          | `Non-Professional: an individual`      | CME ILA         |
| Multi-word          | `Unit of Count: the basis...`          | CME Schedule 2  |
| Numbered            | `(1) "Subscriber" means...`            | OPRA schedules  |
| Lettered            | `(a) Vendor means...`                  | SEC filings     |
| Bulleted            | `• Subscriber means...`                | Various         |
| No article          | `Subscriber means Member`              | CME Schedule 5  |
| The term prefix     | `The term "Subscriber" means...`       | Legal contracts |
| THE TERM (all caps) | `THE TERM "Data" MEANS...`             | Legal headers   |
| Capitalized Means   | `Vendor Means a person...`             | Various         |
| Uppercase MEANS     | `Term MEANS the following...`          | Various         |
| Terms with digits   | `Rule 1A means...`, `Level 2 Data:`    | SEC, exchanges  |
| Digit-start terms   | `10b-5 means...`, `401k Plan means...` | Regulatory docs |
| Terms with &/.      | `S&P 500 Index means...`               | Index providers |
| Smart quotes        | `"Subscriber" means...` (PDF)          | PDF extractions |

### Definition Extraction

Once a chunk is marked as definitions, the `definitions.py` module extracts individual term definitions using patterns:

- `"Term" means/shall mean ...`
- `Term: definition...`
- `Term - definition...`

Extracted definitions are stored in `index/definitions/{source}_definitions.pkl` for auto-linking during query processing.

______________________________________________________________________

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

| Original                                       | Normalized                    |
| ---------------------------------------------- | ----------------------------- |
| "What is the fee schedule for CME data?"       | "fee schedule cme data"       |
| "Can you explain redistribution requirements?" | "redistribution requirements" |
| "How does CME charge for real-time data?"      | "cme charge real-time data"   |

### Usage

The normalized query is used for:

- Vector embedding (OpenAI)
- BM25 keyword search

______________________________________________________________________

## 9. Hybrid Retrieval (Phase 3)

### Strategy

For each query:

1. **Vector search** — `text-embedding-3-large`, k=10
1. **Keyword/BM25 search** — section_heading + chunk text, k=10
1. **Merge** — Deduplicate by chunk_id
1. **Candidate pool** — Maximum 12 chunks

### Retrieval Parameters

| Parameter     | Value | Notes                     |
| ------------- | ----- | ------------------------- |
| Vector k      | 10    | Initial vector retrieval  |
| BM25 k        | 10    | Initial keyword retrieval |
| Candidate max | 12    | Before reranking          |
| Final top     | 3-5   | After reranking           |

______________________________________________________________________

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

______________________________________________________________________

## 11. Confidence Gating (Phase 6)

### Objective

Refuse when evidence is weak or missing. Code-enforced gating prevents hallucinations by skipping the LLM call entirely when retrieval confidence is too low.

### Two-Tier Gating Strategy

The system uses different gating strategies depending on whether scores come from reranking (0-3 scale) or raw retrieval (vector/BM25/RRF scores):

**Tier 1: Reranked Scores (0-3 scale)**

- Used when reranking succeeds
- Threshold-based gating: require chunks ≥ RELEVANCE_THRESHOLD (2)

**Tier 2: Retrieval Scores (raw scores)**

- Used when reranking disabled or fallback triggered
- Ratio-based gating: require top-1/top-2 ratio ≥ 1.2 (clear winner) and top score > 0.05

This prevents false refusals/accepts when reranking is bypassed.

### Rules (Enforced in Code)

**Reranked Scores (0-3):**

| Condition                             | Action |
| ------------------------------------- | ------ |
| No chunks retrieved                   | REFUSE |
| No chunk score ≥ 2                    | REFUSE |
| Top score < 2                         | REFUSE |
| All chunks score 0-1                  | REFUSE |
| Fewer than min_chunks above threshold | REFUSE |

**Retrieval Scores (vector/BM25/RRF):**

| Condition                                   | Action |
| ------------------------------------------- | ------ |
| No chunks retrieved                         | REFUSE |
| Top score ≤ 0.05 (too weak)                 | REFUSE |
| Top-1 / top-2 ratio < 1.2 (no clear winner) | REFUSE |
| Single chunk with score ≤ 0.05              | REFUSE |

### Configuration

**Reranked Score Gating:**

- `RELEVANCE_THRESHOLD = 2` (minimum score to consider chunk RELEVANT)
- `MIN_CHUNKS_REQUIRED = 1` (minimum chunks above threshold to proceed)

**Retrieval Score Gating:**

- `RETRIEVAL_MIN_SCORE = 0.05` (top score must exceed weak positives, prevents near-zero accepts)
- `RETRIEVAL_MIN_RATIO = 1.2` (top-1 / top-2 ≥ 1.2, requires clear winner)

**General:**

- `CONFIDENCE_GATE_ENABLED = True` (enabled by default)

### Implementation

```python
# app/gate.py

def should_refuse(
    chunks: list[Any],
    scores_are_reranked: bool = True,
    relevance_threshold: float = RELEVANCE_THRESHOLD,
    min_chunks: int = MIN_CHUNKS_REQUIRED,
    retrieval_min_score: float = RETRIEVAL_MIN_SCORE,
    retrieval_min_ratio: float = RETRIEVAL_MIN_RATIO,
) -> tuple[bool, str | None]:
    """Determine if query should be refused based on retrieval confidence.

    Two-tier gating:
    - If scores_are_reranked=True: Use 0-3 threshold-based gating
    - If scores_are_reranked=False: Use absolute minimum + gap-based gating
    """
    if not chunks:
        return True, "no_chunks_retrieved"

    if scores_are_reranked:
        # Tier 1: Reranked scores (0-3 scale)
        return _gate_reranked_scores(scores, relevance_threshold, min_chunks)
    else:
        # Tier 2: Retrieval scores (absolute minimum + gap)
        return _gate_retrieval_scores(scores, retrieval_min_score, retrieval_gap)
```

### Integration

Gating happens AFTER reranking but BEFORE budget enforcement:

```python
# In query.py, after reranking:

# Track whether scores are reranked (0-3) or retrieval scores
# Computed once for accuracy and explicitness
scores_are_reranked = enable_reranking and bool(kept_chunks) and not fallback_triggered

if enable_confidence_gate:
    refuse, reason = should_refuse(
        kept_chunks,
        scores_are_reranked=scores_are_reranked,
        relevance_threshold=RELEVANCE_THRESHOLD,
        min_chunks=MIN_CHUNKS_REQUIRED,
        retrieval_min_score=RETRIEVAL_MIN_SCORE,
        retrieval_gap=RETRIEVAL_MIN_GAP,
    )
    if refuse:
        # Skip LLM call entirely
        return {
            "answer": get_refusal_message(sources),
            "refused": True,
            "refusal_reason": reason,
            ...
        }

# Post-budget check: refuse if budget dropped all chunks
if len(all_documents) == 0:
    return {
        "answer": get_refusal_message(sources),
        "refused": True,
        "refusal_reason": "empty_context_after_budget",
        ...
    }
```

### Benefits

1. **Cost Savings**: No LLM call when confidence is low
1. **Accuracy**: Code-enforced refusal (cannot be bypassed by prompts)
1. **Scale-Aware**: Different strategies for reranked vs retrieval scores
1. **Fallback-Safe**: Prevents false refusals when reranking fallback is triggered
1. **Transparency**: Refusal reason logged and returned in response
1. **Configurability**: Can disable with `--no-gate` flag
1. **Post-Budget Safety**: Catches empty context after budget enforcement

______________________________________________________________________

## 12. Context Budget Enforcement (Phase 5)

### Objective

Reduce cost and hallucination risk.

### Targets

| Metric        | Before       | After       |
| ------------- | ------------ | ----------- |
| Avg LLM input | ~100k tokens | ≤60k tokens |

### Rules

- **Accuracy-first prioritization**: Relevance score takes precedence over chunk length
- **Smart budget enforcement**: Drop lowest-score chunks first when over budget
- **Tie-breaking by length**: Prefer shorter chunks when relevance scores are equal
- **Token counting**: Use `tiktoken` for accurate token counting (cl100k_base encoding)
- **Reserved tokens**: Account for system prompt (~500), QA template (~200), answer buffer (~2048)
- **Available context**: ~57k tokens for actual chunks (60k - overheads)

### Implementation

```python
# app/budget.py

import tiktoken

# Configuration
MAX_CONTEXT_TOKENS = 60000  # Total budget
SYSTEM_PROMPT_TOKENS = 500  # System prompt overhead
QA_PROMPT_OVERHEAD = 200    # QA template overhead
ANSWER_BUFFER_TOKENS = 2048 # Reserve for answer
AVAILABLE_CONTEXT_TOKENS = 57300  # For actual chunks

def enforce_context_budget(
    chunks: list[tuple[str, dict[str, Any]]],
    max_tokens: int = AVAILABLE_CONTEXT_TOKENS,
) -> tuple[list[tuple[str, dict]], dict]:
    """Enforce token budget on context chunks.

    Prioritization:
    1. Relevance score (descending) - keep most relevant
    2. Token count (ascending) - prefer shorter when scores tied

    Returns:
        (kept_chunks, budget_info) with metrics
    """
    # Sort by priority: -score (high first), +tokens (short first)
    sorted_chunks = sorted(chunks, key=lambda x: (-x.score, x.tokens))

    # Accumulate until budget exceeded
    kept_chunks = []
    total_tokens = 0

    for chunk, metadata in sorted_chunks:
        formatted = format_chunk_for_context(chunk, metadata)
        tokens = count_tokens(formatted)

        if total_tokens + tokens <= max_tokens:
            kept_chunks.append((chunk, metadata))
            total_tokens += tokens
        # else: drop chunk (over budget)

    return kept_chunks, {
        "kept_count": len(kept_chunks),
        "dropped_count": len(chunks) - len(kept_chunks),
        "total_tokens": total_tokens,
        "under_budget": total_tokens <= max_tokens
    }
```

______________________________________________________________________

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

______________________________________________________________________

## 13. LLM Prompt Discipline (Phase 7)

### Objective

Enforce accuracy-first behavior through comprehensive prompt engineering that complements code-enforced gating. While Phase 6 prevents the LLM from being called with low-confidence retrieval, Phase 7 ensures the LLM responds accurately when it is called.

### Core Principle

> **Accuracy > Cost > Helpfulness**\
> Legal accuracy takes absolute precedence. It is better to refuse than to answer with ANY uncertainty.

### SYSTEM_PROMPT Enhancements

**Strict Rules Section (26 enumerated rules):**

1. **Grounding Requirements (7 rules)**:

   - Answer ONLY using provided context
   - Never use external knowledge, training data, or assumptions
   - Never infer, extrapolate, deduce, or fill gaps
   - Every claim must be traceable to specific quoted text
   - Never "improve" or "clarify" document text - quote verbatim

1. **Mandatory Refusal (6 rules)**:

   - Refuse if complete answer not explicitly in context
   - Exact refusal format: "This is not addressed in the provided [PROVIDER] documents."
   - Explain what specific information is missing
   - Never answer "based on typical practice" - refuse instead
   - Partial information is NOT sufficient - refuse

1. **Citation Requirements (5 rules)**:

   - Always cite documents, sections, and page numbers
   - Citations are mandatory audit trails, not optional
   - Use source-prefixed citations: [CME], [OPRA]
   - Quote exact text for fees, requirements, definitions

1. **Quality Verification (4 rules)**:

   - Before responding: Can you point to exact text for each sentence?
   - Are you making ANY assumptions?
   - Would removing context leave answer unchanged?
   - Are all citations complete and accurate?

**Output Format Requirements:**

Structured format with mandatory sections:

- `## Answer` - Grounded answer with exact refusal format if refusing
- `## Supporting Clauses` - MANDATORY verbatim quotes with citations
- `## Definitions` - Optional, only if defined terms are relevant
- `## Citations` - MANDATORY source document list
- `## Notes` - Optional ambiguities or cross-references

**Forbidden Patterns:**

Explicitly listed patterns to avoid (with visual markers):

- ❌ "Based on typical industry practice..."
- ❌ "While not explicitly stated, it is likely..."
- ❌ "Generally speaking..." or "In most cases..."
- ❌ Providing context-less general knowledge
- ❌ Paraphrasing when exact quotes are needed
- ❌ Answering without citations

**Visual Formatting:**

Uses structured separators (═══) to improve LLM parsing and comprehension. This helps the LLM distinguish between different rule categories and requirements.

### QA_PROMPT Enhancements

**Pre-Response Verification Checklist:**

Mandatory questions the LLM must answer before responding:

1. Can I answer using ONLY the context above? (If NO → refuse)
1. Can I provide specific citations for every claim? (If NO → refuse or remove uncited claims)
1. Am I using ANY external knowledge or assumptions? (If YES → refuse)
1. If definitions provided, am I applying them correctly? (If UNCERTAIN → refuse)

**Refusal Criteria:**

Enumerated conditions that should trigger refusal:

- Context does not contain complete answer
- Any part would require inference or assumption
- Context is ambiguous with multiple interpretations
- Question asks about something not covered
- Would need general knowledge to complete answer

**Accuracy Reminder:**

Explicit reminder at end of prompt:

> "Better to refuse than to answer with uncertainty. Legal accuracy > user satisfaction."

### Implementation Details

**Files Modified:**

- `app/prompts.py`: Complete rewrite of SYSTEM_PROMPT and QA_PROMPT templates
- `tests/test_prompts.py`: 40 new validation tests
- `tests/test_budget.py`: Adjusted token budget test for longer prompts

**Token Impact:**

Enhanced prompts are ~800 tokens longer than original (now ~2500 tokens vs ~1700 tokens). This is an intentional trade-off for accuracy:

- Cost increase: ~$0.002 per query (~7% of total)
- Benefit: Significantly reduced hallucination risk
- Rationale: Accuracy-first principle justifies additional tokens

### Testing

**Test Coverage (40 tests):**

- 12 tests for SYSTEM_PROMPT structure and requirements
- 10 tests for QA_PROMPT templates and placeholders
- 4 tests for refusal message generation
- 3 tests for prompt integration
- 5 tests for accuracy requirements enforcement
- 6 tests for format enforcement

**Validation:**

- ✅ All prompts contain strict rules
- ✅ Refusal instructions are explicit
- ✅ Citation requirements are mandatory
- ✅ Quality verification checklists present
- ✅ Forbidden patterns enumerated
- ✅ Output format clearly specified

### Deviations from Original Spec

The implementation goes beyond the basic spec requirements with enhancements that add value:

1. **Pre-response Verification Checklists**: Not in original spec, but critical for accuracy
1. **Forbidden Patterns Section**: Visual examples of what NOT to do
1. **Structured Formatting**: Separator lines for improved LLM comprehension
1. **Enumerated Refusal Criteria**: Specific conditions for refusal
1. **Quality Verification Section**: Numbered checklist before responding
1. **Verbatim Quote Requirement**: Strengthened beyond basic "quote" to explicit anti-paraphrasing
1. **Accuracy-First Principle Emphasis**: Made explicit throughout prompts

**Rationale:** These enhancements align with the project's core principle that "The LLM is not a knowledge source—it is only the renderer" and the accuracy-first philosophy stated in README.md.

### Benefits

1. **Reduced Hallucinations**: Multi-layered accuracy enforcement
1. **Consistent Refusals**: Explicit refusal format and criteria
1. **Audit Trail**: Mandatory citations enable verification
1. **Quality Assurance**: Built-in verification steps
1. **Legal Defensibility**: Structured output with clear provenance
1. **Cost-Effective**: Accuracy reduces need for human review/correction

______________________________________________________________________

## 14. Debug & Audit Mode (Phase 8)

### 14.1 Debug Mode (Pipeline Transparency)

**Purpose**: Provide complete visibility into the query pipeline for troubleshooting and optimization.

**Output Destinations**:

- **Console (stderr)**: Real-time JSON output when `--debug` flag used
- **File**: Always writes to `logs/debug.jsonl` (rotating, 10MB, 5 backups)

**CLI Usage**:

```bash
rag query "fee schedule" --debug
```

**Debug Output Format**:

```json
{
  "timestamp": "2026-01-29T10:15:30.123456Z",
  "original_query": "What is the fee schedule?",
  "normalized_query": "fee schedule",
  "retrieval": {
    "vector": {"count": 10, "top_score": 0.85},
    "bm25": {"count": 10, "top_score": 12.3},
    "merged": {"count": 12, "unique_chunks": 12}
  },
  "reranking": {
    "input_chunks": 12,
    "kept_chunks": 3,
    "dropped_chunks": 9,
    "scores": [
      {"chunk_id": "cme_fees_schedule.pdf_0", "score": 3, "kept": true},
      {"chunk_id": "cme_fees_schedule.pdf_1", "score": 2, "kept": true},
      {"chunk_id": "cme_general_terms.pdf_5", "score": 0, "kept": false}
    ]
  },
  "confidence_gate": {
    "enabled": true,
    "passed": true,
    "top_score": 3,
    "threshold": 2,
    "min_chunks_required": 1,
    "chunks_above_threshold": 2
  },
  "budget": {
    "target_tokens": 60000,
    "final_tokens": 4523,
    "chunks_kept": 3,
    "chunks_dropped": 0,
    "under_budget": true
  },
  "llm": {
    "model": "gpt-4.1",
    "prompt_tokens": 4523,
    "completion_tokens": 234,
    "total_tokens": 4757
  },
  "answer_generated": true,
  "latency_ms": 3421
}
```

**Implementation**:

- Created `app/debug.py` module with `log_debug_info()` function
- Rotating file handler prevents unbounded disk growth
- ISO 8601 UTC timestamps for audit compliance
- Integrated at all query pipeline stages

### 14.2 Query/Response Audit Logging (Compliance)

**Purpose**: Track all queries and responses for compliance, usage analytics, and cost monitoring. Separate from debug mode - debug is for troubleshooting, audit is for business metrics.

**Key Differences from Debug Mode**:

| Feature         | Debug Mode              | Audit Logging              |
| --------------- | ----------------------- | -------------------------- |
| **Purpose**     | Troubleshooting         | Compliance/analytics       |
| **Verbosity**   | High (pipeline details) | Low (business metrics)     |
| **Activation**  | Optional (`--debug`)    | Always on                  |
| **Console Out** | Yes (stderr)            | Optional (`--log-queries`) |
| **File Output** | `logs/debug.jsonl`      | `logs/queries.jsonl`       |
| **Rotation**    | 10MB x 5 (50MB)         | 50MB x 10 (500MB)          |

**Configuration** (`app/config.py`):

```python
# Query/Response Audit Logging
AUDIT_LOG_FILE = LOGS_DIR / "queries.jsonl"
AUDIT_LOG_MAX_BYTES = 50 * 1024 * 1024  # 50MB per file
AUDIT_LOG_BACKUP_COUNT = 10  # Keep 10 old files (500MB total)
```

**CLI Usage**:

```bash
# File logging only (default)
rag query "What is the CME market data fee?"

# File + console logging
rag query "What is the CME market data fee?" --log-queries
```

**Audit Log Format** (`logs/queries.jsonl`):

```json
{
  "timestamp": "2026-01-29T10:15:30.123456Z",
  "query": "What is the CME market data fee for real-time equity quotes?",
  "answer": "## Answer\nThe CME market data fee for real-time equity quotes is $15/month per device...",
  "sources": ["cme"],
  "chunks_retrieved": 12,
  "chunks_used": 3,
  "tokens_input": 4523,
  "tokens_output": 234,
  "latency_ms": 3421,
  "refused": false,
  "refusal_reason": null,
  "user_id": null
}
```

**Tracked Metrics**:

- `timestamp`: ISO 8601 UTC
- `query`: Original user input
- `answer`: LLM response or refusal message
- `sources`: Data sources queried (e.g., ["cme"])
- `chunks_retrieved`: Count before reranking
- `chunks_used`: Count after reranking + budget enforcement
- `tokens_input`: Prompt tokens (for cost tracking)
- `tokens_output`: Completion tokens (for cost tracking)
- `latency_ms`: Total query time (for performance monitoring)
- `refused`: Boolean (was query refused?)
- `refusal_reason`: Why refused (e.g., "confidence_too_low", "no_chunks_retrieved", "empty_context_after_budget")
- `user_id`: Future API authentication (null for CLI)

**Implementation**:

- Created `app/audit.py` module with `log_query_response()` function
- Rotating file handler with 500MB total capacity (50MB x 10 files)
- Always writes to file (compliance requirement)
- Optional stderr output via `--log-queries` flag
- Integrated at all 4 query exit points:
  1. No chunks retrieved
  1. Confidence gate refusal
  1. Budget enforcement dropped all chunks
  1. Successful response
- Latency tracking via `time.time()` and `calculate_latency_ms()`
- Token counting via `app.budget.count_tokens()`

**Privacy & Compliance**:

- Log rotation prevents unbounded disk usage
- Future: PII redaction/hashing option
- Future: GDPR compliance for user data (when API added)
- Current: No PII collected (CLI only, no user identification)

______________________________________________________________________

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

| Metric             | Description               | Target |
| ------------------ | ------------------------- | ------ |
| Chunk Recall       | Expected chunks retrieved | ≥90%   |
| Refusal Accuracy   | Correct refusals          | 100%   |
| False Refusal Rate | Incorrect refusals        | \<5%   |

______________________________________________________________________

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

______________________________________________________________________

## 17. Cost Estimation

### Per Query

| Operation             | Tokens | Cost             |
| --------------------- | ------ | ---------------- |
| Embedding (query)     | ~50    | $0.000002        |
| Reranking (10 chunks) | ~2,500 | $0.005           |
| Answer generation     | ~3,200 | $0.011           |
| **Total**             |        | **~$0.02/query** |

### Monthly (100 queries/day)

| Usage  | Queries | Cost  |
| ------ | ------- | ----- |
| Light  | 3,000   | ~$60  |
| Medium | 6,000   | ~$120 |
| Heavy  | 10,000  | ~$200 |

______________________________________________________________________

## 19. Expected Outcomes

After implementation:

- ✅ Conversational queries map to correct clauses
- ✅ Irrelevant context is eliminated (reranking)
- ✅ Refusals are reliable and boring (code-enforced)
- ✅ Input token usage drops materially (≤60k)
- ✅ Cost per query is predictable (~$0.02)
- ✅ Answers are auditable and defensible (debug mode)
- ✅ Evaluation set validates retrieval accuracy
