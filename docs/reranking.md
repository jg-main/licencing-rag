# LLM Reranking Guide

This guide explains how the system uses GPT-4.1 to score and filter retrieved chunks.

## Overview

Reranking refines hybrid search results by scoring each chunk's relevance:

```
Hybrid Search (returns 10 chunks)
    ↓
LLM Reranking (scores 0-3 for each)
    ↓
Top-N Chunks (keeps highest-scoring)
    ↓
Confidence Gate
```

**Why rerank?**

- Hybrid search uses cosine similarity and BM25 (statistical)
- LLM understands semantic relevance and context
- Filters out chunks that match keywords but don't answer question

## Scoring Scale

| Score | Label             | Meaning                                             |
| ----- | ----------------- | --------------------------------------------------- |
| 3     | HIGHLY RELEVANT   | Directly answers question or contains critical info |
| 2     | RELEVANT          | Useful context that helps answer question           |
| 1     | SOMEWHAT RELEVANT | Mentions related topics but doesn't directly help   |
| 0     | NOT RELEVANT      | About different topics entirely                     |

## How It Works

### 1. Retrieve Chunks

Hybrid search returns top-K chunks (default: 10)

### 2. Score Each Chunk

LLM scores each chunk independently:

**Prompt:**

```
You are a relevance scoring expert for a license agreement QA system.

Score how relevant this chunk is to answering the question:

Question: {user_question}

Chunk:
{chunk_text}

Score (0-3): [Your score]
Explanation: [Why this score]
```

**Model:** GPT-4.1 (same as answer generation)

### 3. Parse Scores

Extract numeric score (0-3) and explanation from LLM response:

```json
{
  "score": 3,
  "explanation": "Chunk contains exact definition of subscriber term."
}
```

### 4. Sort and Filter

- Sort chunks by score (descending)
- Keep only chunks with score ≥ 2 (configurable)
- Limit to top-N chunks (default: 5)

### 5. Pass to Confidence Gate

Reranked chunks proceed to gating logic.

## Configuration

**Edit `app/config.py`:**

```python
# Reranking parameters
MAX_CHUNKS_AFTER_RERANKING = 5      # Keep top-N chunks
MIN_RERANKING_SCORE = 2              # Minimum score to keep (2 = RELEVANT)
RERANKING_INCLUDE_EXPLANATIONS = True  # Include LLM explanations
RERANKING_TIMEOUT = 30               # Seconds per chunk
```

## Performance

**Cost:** ~$0.005 per query (10 chunks × ~250 tokens each, 1 token output)

**Latency:** ~1-2 seconds (parallel scoring)

**Parallelization:** Scores chunks concurrently (ThreadPoolExecutor)

## Impact on Accuracy

**Before reranking (hybrid search only):**

- Chunk recall: 75%
- False positives: Common (keyword matches without semantic relevance)

**After reranking (hybrid + LLM scoring):**

- Chunk recall: 87.5%
- False positives: Rare (LLM filters irrelevant matches)

## Examples

### Example 1: Definition Query

**Question:** "What is a subscriber?"

**Hybrid Search Results:**

| Chunk | Source | BM25 Score | Vector Score | Text Preview                       |
| ----- | ------ | ---------- | ------------ | ---------------------------------- |
| 1     | cme    | 0.85       | 0.92         | "Subscriber means any individual…" |
| 2     | cme    | 0.45       | 0.78         | "Subscriber fees are listed in…"   |
| 3     | cme    | 0.30       | 0.65         | "Non-subscriber access requires…"  |

**Reranking Scores:**

| Chunk | LLM Score | Explanation                                           |
| ----- | --------- | ----------------------------------------------------- |
| 1     | 3         | "Direct definition of subscriber term"                |
| 2     | 1         | "Mentions subscribers but about fees, not definition" |
| 3     | 1         | "Contrasts with subscribers, not a definition"        |

**Final Selection:** Chunk 1 only (score ≥ 2)

### Example 2: Multi-Part Question

**Question:** "What are the fees and requirements for redistribution?"

**Hybrid Search Results:**

| Chunk | Source | Text Preview                                   |
| ----- | ------ | ---------------------------------------------- |
| 1     | cme    | "Redistribution fee is $500 per month…"        |
| 2     | cme    | "Redistribution requires written consent…"     |
| 3     | cme    | "Subscriber fees do not cover redistribution…" |
| 4     | cme    | "Display use is distinct from redistribution…" |

**Reranking Scores:**

| Chunk | LLM Score | Explanation                              |
| ----- | --------- | ---------------------------------------- |
| 1     | 3         | "Direct answer to fees part of question" |
| 2     | 3         | "Direct answer to requirements part"     |
| 3     | 2         | "Related context about fee structure"    |
| 4     | 0         | "About display use, not redistribution"  |

**Final Selection:** Chunks 1, 2, 3 (scores ≥ 2)

## Debug Mode

View reranking scores:

```bash
rag query --debug "What is a subscriber?"

# Output shows:
# Reranking results:
# - Chunk 1: score=3, "Direct definition"
# - Chunk 2: score=1, "About fees, not definition"
# - Chunk 3: score=1, "Contrasts with subscribers"
#
# Kept 1 chunks with score >= 2
```

## Troubleshooting

### "All chunks filtered out"

**Cause:** No chunks scored ≥ MIN_RERANKING_SCORE

**Solutions:**

- Lower threshold: `MIN_RERANKING_SCORE = 1`
- Check if question is answerable from documents
- Try different search mode (`--search-mode vector`)

### "Reranking timeout"

**Cause:** LLM taking too long per chunk

**Solutions:**

- Increase timeout: `RERANKING_TIMEOUT = 60`
- Check OpenAI API status
- Reduce chunk length: `MAX_CHUNK_LENGTH_FOR_RERANKING = 2000`

### "Unexpected scores"

**Cause:** LLM misinterpreting question or chunk

**Solutions:**

- Review with `--debug` to see explanations
- Check if chunks are actually relevant (search quality issue)
- Adjust prompt in `app/rerank.py` if consistently wrong

## Advanced: Custom Scoring Criteria

**Edit `app/rerank.py` to customize scoring prompt:**

```python
RERANKING_SYSTEM_PROMPT = """You are a relevance scoring expert.

Use this 4-point scale:
- Score 3: {your custom criteria}
- Score 2: {your custom criteria}
- Score 1: {your custom criteria}
- Score 0: {your custom criteria}

Focus on: {your domain-specific guidance}
"""
```

**Example customization:**

- Prioritize recent documents
- Weight certain sections higher (e.g., fees > definitions)
- Account for jurisdiction-specific rules

## Disabling Reranking

**Not recommended**, but possible:

```python
# app/config.py
ENABLE_RERANKING = False  # (requires code change)
```

**Effect:** Falls back to retrieval scores only. Confidence gate uses different logic.

## See Also

- [Confidence Gating Guide](confidence-gating.md) - Next pipeline stage
- [Hybrid Search Guide](hybrid-search.md) - Previous pipeline stage
- [Cost Estimation](cost-estimation.md) - Reranking cost breakdown
- [Configuration Guide](configuration.md) - All settings
