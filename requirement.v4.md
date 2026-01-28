# CME Licensing RAG — Requirement

______________________________________________________________________

## 1. Goal

Build a **high-precision, clause-level Retrieval-Augmented Generation (RAG) system** for CME licensing documents that:

- Answers **natural-language licensing questions**
- Retrieves the **exact contractual clauses**
- **Refuses deterministically** when documents are silent
- Produces **auditable citations**
- Minimizes hallucinations and irrelevant context
- Is deployable behind an API (FastAPI) and callable from Slack

This system is intended for **licensing interpretation and internal decision support**, not general chat.

______________________________________________________________________

## 2. Model Stack

### Embeddings

- **Provider:** OpenAI
- **Model:** `text-embedding-3-large`
- **Usage:**
  - Document chunk embeddings (ingestion, one-time)
  - Query embeddings (per request)

### LLM Reasoning Model

- **Provider:** OpenAI
- **Model:** `gpt-4.1`
- **Usage:**
  - Clause-grounded answer generation
  - Reranking / relevance scoring
  - Comparative reasoning across retrieved clauses

> ⚠️ Any change to these models is a **breaking change** and requires explicit review.

______________________________________________________________________

## 3. Non-Negotiable Design Principles

1. **Retrieval quality > LLM cleverness**
1. **The LLM is not a knowledge source**
1. **Refusal is enforced in code, not only via prompt**
1. **Context trimming is mandatory (quality + cost control)**
1. **All answers must be traceable to documents**
1. **Single provider only (OpenAI)**

______________________________________________________________________

## 4. Phase 1 — Embeddings Upgrade

### Objective

Maximize semantic recall for legal and contractual clauses.

### Tasks

- Replace all local embeddings with **OpenAI `text-embedding-3-large`**
- Re-embed all existing document chunks
- Store embedding model metadata with the vector index
- Block querying if:
  - index embedding model ≠ runtime embedding model

### Acceptance Criteria

Queries such as:

- `fee schedule`
- `what is the fee schedule?`
- `how does CME charge for this data?`

retrieve the **same top clauses**.

______________________________________________________________________

## 4. Phase 2 — Query Normalization (Pre-Retrieval)

### Objective

Ensure conversational questions behave like keyword queries.

### Tasks

Implement deterministic normalization:

- Lowercase
- Strip leading phrases:
  - `what is`
  - `can you`
  - `please explain`
  - `how does`
- Remove filler words (fixed list)
- Preserve nouns and legal terms

### Example

- "What is the fee schedule for CME data?" → "fee schedule CME data"

### Usage

The normalized query must be used for:

- Vector embeddings
- Keyword/BM25 retrieval

______________________________________________________________________

## 5. Phase 3 — Hybrid Retrieval (Mandatory)

### Objective

Avoid missed clauses due to embedding limitations.

### Retrieval Strategy

For each query:

1. **Vector search**
   - Model: `text-embedding-3-large`
   - k = 10
1. **Keyword / BM25 search**
   - Fields:
     - `section_heading`
     - chunk text
   - k = 10
1. **Merge results**
   - Deduplicate by `chunk_id`
1. **Candidate pool**
   - Maximum 12 chunks

### Acceptance Criteria

- Fee schedules, exhibits, and tables are retrievable even with loose phrasing.

______________________________________________________________________

## 6. Phase 4 — Reranking (Precision Pass)

### Objective

Remove irrelevant chunks before the LLM sees them.

### Tasks

- Use **`gpt-4.1` in scoring mode** (not answer mode)
- Prompt example (internal only):
  > “Score this chunk from 0–3 for relevance to the question. Output only the score.”

### Rules

- Score all candidate chunks
- Keep top **3–5** chunks only
- Discard all others

______________________________________________________________________

## 7. Phase 5 — Context Budget Enforcement

### Objective

Reduce cost and hallucination risk.

### Targets

- Reduce average LLM input from ~100k tokens → **≤60k tokens**

### Rules

- Hard cap on number of chunks
- Prefer:
  - shorter clauses
  - higher relevance scores
- Drop long, low-score chunks first

______________________________________________________________________

## 8. Phase 6 — Retrieval Confidence Gating

### Objective

Refuse when evidence is weak or missing.

### Rules (Enforced in Code)

- If no chunk score ≥ relevance threshold → **refuse**
- If top score < confidence threshold → **refuse**
- If score gap between #1 and #2 is large → keep only #1

### Standard Refusal Text

- "Not addressed in the provided CME documents."

______________________________________________________________________

## 9. Phase 7 — LLM Prompt Discipline (`gpt-4.1`)

### System Prompt Requirements

- Use **only** provided context
- No extrapolation or general legal knowledge
- Mandatory citations
- Explicit refusal when unsupported

### Output Format (Strict)

```
Answer: <concise, clause-grounded answer>

Citations: <Document | Section | Page range>
```

______________________________________________________________________

## 10. Phase 8 — Debug & Audit Mode (Required)

### Add a debug flag that logs

- Original query
- Normalized query
- Retrieved chunks + relevance scores
- Dropped chunks + reason
- Final context token count

### Purpose

- Trust
- Cost analysis
- Ongoing tuning

______________________________________________________________________

## 11. Phase 9 — Evaluation Set

### Tasks

Create `eval/questions.json` with:

- ~20 representative licensing questions
- Expected clause(s) (by section or chunk ID)
- Expected refusal cases

### Goal

Validate **clause retrieval accuracy**, not prose quality.

______________________________________________________________________

## 12. Explicitly Out of Scope

- Conversation memory
- Increasing chunk size
- Prompt-only fixes for retrieval
- Using the LLM to infer missing terms
- External browsing or general legal knowledge

______________________________________________________________________

## 13. Expected Outcome

After implementation:

- Conversational queries map to correct clauses
- Irrelevant context is eliminated
- Refusals are reliable and boring
- Input token usage drops materially
- Cost per 1,000 queries decreases
- Answers are auditable and defensible

______________________________________________________________________

## 14. Final Directive to Developer

> Build this system with **precision and reliability as the highest priorities**. Start with current implmentation and incrementally add each phase. No need to keep backward compatibility with prior versions. Delete any legacy code that conflicts with these requirements. The reasoning model is OpenAI `gpt-4.1`.\
> Treat retrieval, reranking, and context trimming as the product; the LLM is only the renderer.\*\*
