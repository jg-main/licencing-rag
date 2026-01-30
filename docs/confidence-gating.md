# Confidence Gating Guide

This guide explains how the system refuses to answer when evidence is weak.

## Overview

Confidence gating is a **code-enforced refusal mechanism** that prevents answering questions when retrieval confidence is too low.

**Key principle:** Better to refuse than hallucinate.

```
Reranked Chunks
    ↓
Confidence Gate  ← Evaluates evidence strength
    ↓
    ├─ Pass → Continue to LLM
    └─ Fail → Refuse (skip LLM entirely)
```

**Benefits:**

- Prevents hallucinations from weak evidence
- Saves cost by skipping LLM call
- Cannot be bypassed by prompt engineering
- Transparent refusal reasons

## Gating Logic

### Two-Tier Strategy

**Tier 1: Reranked Scores (0-3 scale)**

Used when LLM reranking is enabled (default).

**Tier 2: Retrieval Scores (vector/BM25/RRF)**

Used when reranking disabled or fails.

### Reranked Score Gating

**Thresholds:**

- `RELEVANCE_THRESHOLD = 2` (minimum score: 2 = RELEVANT)
- `MIN_CHUNKS_REQUIRED = 1` (at least 1 chunk above threshold)

**Refusal conditions:**

1. **No chunks retrieved**

   ```
   Refuse: "No relevant information found in documents"
   ```

1. **Top chunk score < 2**

   ```
   Refuse: "Retrieved information not sufficiently relevant"
   ```

1. **Fewer than 1 chunk with score ≥ 2**

   ```
   Refuse: "Insufficient high-confidence chunks"
   ```

**Pass conditions:**

- At least 1 chunk with score ≥ 2
- Top chunk score ≥ 2

### Retrieval Score Gating

**Thresholds:**

- `RETRIEVAL_MIN_SCORE = 0.05` (absolute minimum)
- `RETRIEVAL_MIN_RATIO = 1.2` (top-1 must be ≥ 1.2 × top-2)

**Refusal conditions:**

1. **No chunks retrieved**

   ```
   Refuse: "No relevant information found"
   ```

1. **Top score < 0.05**

   ```
   Refuse: "All retrieval scores too low"
   ```

1. **Top-1/Top-2 ratio < 1.2**

   ```
   Refuse: "No clear winner among results"
   ```

**Pass conditions:**

- Top score ≥ 0.05
- Top-1 score ≥ 1.2 × Top-2 score (clear winner)

## Examples

### Example 1: Successful Pass

**Question:** "What is a subscriber?"

**Reranked chunks:**

- Chunk 1: score=3 (definition chunk)
- Chunk 2: score=1 (fee chunk)

**Gate evaluation:**

- ✅ At least 1 chunk retrieved
- ✅ Top score (3) ≥ threshold (2)
- ✅ Chunks above threshold: 1 ≥ required (1)

**Result:** PASS → Proceed to LLM

### Example 2: Refusal (Weak Evidence)

**Question:** "What is the weather in Chicago?"

**Reranked chunks:**

- Chunk 1: score=0 (CME location mention)
- Chunk 2: score=0 (unrelated)

**Gate evaluation:**

- ✅ At least 1 chunk retrieved
- ❌ Top score (0) < threshold (2)
- ❌ Chunks above threshold: 0 < required (1)

**Result:** REFUSE

**Refusal message:**

```
I cannot answer this question based on the available documents.
The retrieved information is not sufficiently relevant.

Reason: Top chunk relevance score (0) below threshold (2)
```

### Example 3: Refusal (No Clear Winner)

**Question:** "What are the fees?" (when using retrieval scores)

**Retrieval chunks:**

- Chunk 1: score=0.06 (fee schedule)
- Chunk 2: score=0.055 (similar fee chunk)

**Gate evaluation:**

- ✅ At least 1 chunk retrieved
- ✅ Top score (0.06) ≥ minimum (0.05)
- ❌ Ratio: 0.06 / 0.055 = 1.09 < 1.2 (not clear winner)

**Result:** REFUSE

**Refusal message:**

```
I cannot answer this question based on the available documents.
No clear best match among retrieved results.

Reason: Top-1/Top-2 ratio (1.09) below threshold (1.2)
```

## Configuration

**Edit `app/config.py` or `app/gate.py`:**

```python
# Reranked score gating
RELEVANCE_THRESHOLD = 2        # Minimum 0-3 score (2 = RELEVANT)
MIN_CHUNKS_REQUIRED = 1        # Minimum chunks above threshold

# Retrieval score gating (fallback)
RETRIEVAL_MIN_SCORE = 0.05     # Absolute minimum score
RETRIEVAL_MIN_RATIO = 1.2      # Top-1/Top-2 clear winner ratio
```

**Impact of changing thresholds:**

| Setting               | Increase Effect                   | Decrease Effect            |
| --------------------- | --------------------------------- | -------------------------- |
| `RELEVANCE_THRESHOLD` | More refusals (stricter)          | Fewer refusals (riskier)   |
| `MIN_CHUNKS_REQUIRED` | More refusals (need consensus)    | Fewer refusals (single OK) |
| `RETRIEVAL_MIN_SCORE` | More refusals (higher bar)        | Fewer refusals (lower bar) |
| `RETRIEVAL_MIN_RATIO` | More refusals (need clear winner) | Fewer refusals (ties OK)   |

## Evaluation Metrics

**Gating effectiveness measured by:**

1. **Refusal Accuracy** - Correct refusals / Total should-refuse
1. **False Refusal Rate** - Incorrect refusals / Total should-answer
1. **False Acceptance Rate** - Incorrect answers / Total should-refuse

**Current results (v0.4):**

- Refusal Accuracy: 100%
- False Refusal: 0%
- False Acceptance: 0%

## Debug Mode

See gating decision:

```bash
rag query --debug "What is a subscriber?"

# Output shows:
# Confidence Gate:
#   Top chunk score: 3
#   Chunks above threshold (2): 1
#   Decision: PASS
#
# Or:
# Confidence Gate:
#   Top chunk score: 1
#   Chunks above threshold (2): 0
#   Decision: REFUSE
#   Reason: Top chunk relevance score (1) below threshold (2)
```

## When Gating Happens

**Early in pipeline (before LLM call):**

```
Query Normalization
    ↓
Embedding
    ↓
Hybrid Search
    ↓
LLM Reranking
    ↓
Confidence Gate  ← HERE (before expensive LLM call)
    ↓
Context Budget
    ↓
Answer Generation (only if gate passed)
```

**Why early?**

- Saves cost (no LLM call for weak queries)
- Prevents hallucinations (LLM never sees weak evidence)
- Faster response (skip LLM latency)

## Best Practices

1. **Monitor refusal rate** - Too high? Lower thresholds. Too low? Increase thresholds.
1. **Review refusals** - Use `--debug` to understand why queries refused
1. **Tune with eval set** - Test threshold changes against evaluation questions
1. **Document tuning** - Track threshold changes and their impact

## Troubleshooting

### "Too many refusals"

**Cause:** Thresholds too strict or poor document coverage

**Solutions:**

- Lower `RELEVANCE_THRESHOLD` (e.g., 1 instead of 2)
- Check if documents actually contain answer
- Try different search mode (`--search-mode hybrid`)
- Review with `--debug` to see scores

### "False acceptances"

**Cause:** Thresholds too lenient

**Solutions:**

- Increase `RELEVANCE_THRESHOLD` (e.g., 3 instead of 2)
- Increase `MIN_CHUNKS_REQUIRED` (e.g., 2 instead of 1)
- Increase `RETRIEVAL_MIN_RATIO` (e.g., 1.5 instead of 1.2)

### "Inconsistent behavior"

**Cause:** Switching between reranked and retrieval gating

**Solutions:**

- Always enable reranking for consistency
- Check logs to see which gating tier was used
- Ensure reranking not timing out (increase timeout)

## Advanced: Custom Gating Logic

**Edit `app/gate.py` for domain-specific rules:**

```python
def should_refuse(chunks, scores_are_reranked=True, **kwargs):
    """Custom gating logic."""

    # Example: Always refuse if question contains "weather"
    if "weather" in original_question.lower():
        return True, "Questions about weather not supported"

    # Example: Require 2+ chunks for multi-part questions
    if "and" in original_question or "or" in original_question:
        if len([c for c in chunks if c.score >= 2]) < 2:
            return True, "Multi-part question requires more evidence"

    # ... normal gating logic ...
```

## Disabling Gating

**Not recommended**, but possible for debugging:

```python
# app/gate.py
def should_refuse(chunks, **kwargs):
    return False, None  # Never refuse (DANGEROUS)
```

**Effect:** System will attempt to answer every question, even with weak evidence. High hallucination risk.

## See Also

- [Reranking Guide](reranking.md) - Previous pipeline stage (provides scores)
- [Debug Mode Guide](debug-mode.md) - Inspect gating decisions
- [Configuration Guide](configuration.md) - Threshold settings
- [Evaluation Framework](development/implementation-plan.md#phase-9) - Testing gating accuracy
