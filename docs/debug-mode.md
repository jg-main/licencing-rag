# Debug Mode Guide

This guide explains how to use debug mode for pipeline transparency and troubleshooting.

## Overview

Debug mode provides complete visibility into the query pipeline:

```
rag query --debug "What is a subscriber?"
```

**Output locations:**

- **stderr:** Real-time debug output (human-readable)
- **logs/debug.jsonl:** Machine-parsable audit trail

## What Debug Mode Shows

### 1. Query Normalization

```
Original query: What is a subscriber?
Normalized query: subscriber
```

### 2. Embedding Generation

```
Embedding model: text-embedding-3-large
Embedding dimensions: 3072
Tokens used: 3
```

### 3. Hybrid Search Results

```
Search mode: hybrid
Sources: cme

Vector search results: 10 chunks
  - Chunk cme__definitions__chunk_5: score=0.92
  - Chunk cme__fees__chunk_12: score=0.78
  - ...

BM25 search results: 10 chunks
  - Chunk cme__definitions__chunk_5: score=2.45
  - Chunk cme__agreements__chunk_8: score=1.83
  - ...

RRF fusion results: 10 chunks
  - Chunk cme__definitions__chunk_5: score=0.0328
  - Chunk cme__fees__chunk_12: score=0.0312
  - ...
```

### 4. LLM Reranking

```
Reranking 10 chunks with GPT-4.1

Chunk 1 (cme__definitions__chunk_5):
  Relevance score: 3
  Explanation: "Direct definition of subscriber term"

Chunk 2 (cme__fees__chunk_12):
  Relevance score: 1
  Explanation: "Mentions subscribers but about fees"

...

Kept 3 chunks with score >= 2
```

### 5. Confidence Gate

```
Confidence gate evaluation:
  Mode: reranked
  Top chunk score: 3
  Chunks above threshold (2): 3
  Decision: PASS
```

Or:

```
Confidence gate evaluation:
  Mode: reranked
  Top chunk score: 1
  Chunks above threshold (2): 0
  Decision: REFUSE
  Reason: Top chunk relevance score (1) below threshold (2)
```

### 6. Context Budget

```
Context budget enforcement:
  Max tokens: 60000
  Chunks after reranking: 3
  Total chunk tokens: 2450
  System prompt tokens: 180
  Question tokens: 3
  Total context tokens: 2633
  Budget remaining: 57367 tokens
  Chunks removed: 0
```

### 7. LLM Call

```
Generating answer with GPT-4.1

Prompt tokens: 2633
System prompt: "You are a legal research assistant..."
User prompt: "Question: What is a subscriber?\n\nContext:\n[3 chunks]"

Response received:
  Completion tokens: 145
  Total tokens: 2778
  Cost: $0.0278
```

### 8. Output Validation

```
Validating answer format:
  Has answer field: ✓
  Has supporting_clauses: ✓
  Has citations: ✓
  Has metadata: ✓
  Format: valid
```

### 9. Audit Log

```
Query logged to logs/queries.jsonl:
  Query ID: q_1738284730_abc123
  Timestamp: 2026-01-30T15:45:30.123456Z
  Answer length: 145 tokens
  Chunks used: 3
  Total cost: $0.0278
```

## JSON Log Format

**File:** `logs/debug.jsonl` (one JSON object per line)

**Structure:**

```json
{
  "timestamp": "2026-01-30T15:45:30.123456Z",
  "query_id": "q_1738284730_abc123",
  "original_query": "What is a subscriber?",
  "normalized_query": "subscriber",
  "embedding": {
    "model": "text-embedding-3-large",
    "dimensions": 3072,
    "tokens": 3
  },
  "retrieval": {
    "mode": "hybrid",
    "sources": ["cme"],
    "vector_results": 10,
    "bm25_results": 10,
    "rrf_results": 10,
    "per_source_results": {
      "cme": {
        "vector_chunks": ["cme__definitions__chunk_5", ...],
        "bm25_chunks": ["cme__definitions__chunk_5", ...],
        "rrf_chunks": ["cme__definitions__chunk_5", ...]
      }
    }
  },
  "reranking": {
    "enabled": true,
    "chunks_scored": 10,
    "chunks_kept": 3,
    "scores": [
      {
        "chunk_id": "cme__definitions__chunk_5",
        "score": 3,
        "explanation": "Direct definition of subscriber term"
      },
      ...
    ]
  },
  "confidence_gate": {
    "mode": "reranked",
    "decision": "pass",
    "top_score": 3,
    "chunks_above_threshold": 3,
    "threshold": 2,
    "reason": null
  },
  "budget": {
    "max_tokens": 60000,
    "chunks_before": 3,
    "chunks_after": 3,
    "total_tokens": 2633,
    "budget_used": 2633,
    "budget_remaining": 57367,
    "chunks_removed": 0
  },
  "llm": {
    "model": "gpt-4.1",
    "prompt_tokens": 2633,
    "completion_tokens": 145,
    "total_tokens": 2778,
    "cost": 0.0278
  },
  "validation": {
    "format": "valid",
    "has_answer": true,
    "has_supporting_clauses": true,
    "has_citations": true
  },
  "total_duration_ms": 1420
}
```

## Usage Examples

### Basic Debug

```bash
rag query --debug "What is a subscriber?"
```

### Debug with JSON Output

```bash
rag query --debug --format json "What are the fees?" > result.json
```

### Debug Specific Source

```bash
rag query --debug --source cme "What is a subscriber?"
```

### Debug Different Search Mode

```bash
rag query --debug --search-mode vector "What are the fees?"
```

## Analyzing Debug Logs

### View Recent Queries

```bash
# Show last 5 debug logs
tail -5 logs/debug.jsonl | jq .
```

### Filter by Decision

```bash
# Show all refused queries
jq 'select(.confidence_gate.decision == "refuse")' logs/debug.jsonl

# Show all passed queries
jq 'select(.confidence_gate.decision == "pass")' logs/debug.jsonl
```

### Analyze Costs

```bash
# Total cost across all queries
jq -s 'map(.llm.cost) | add' logs/debug.jsonl

# Average cost per query
jq -s 'map(.llm.cost) | add / length' logs/debug.jsonl

# Most expensive queries
jq -s 'sort_by(-.llm.cost) | .[0:5]' logs/debug.jsonl
```

### Analyze Performance

```bash
# Average query duration
jq -s 'map(.total_duration_ms) | add / length' logs/debug.jsonl

# Slowest queries
jq -s 'sort_by(-.total_duration_ms) | .[0:5]' logs/debug.jsonl
```

### Analyze Retrieval

```bash
# See which chunks are retrieved most often
jq -r '.reranking.scores[].chunk_id' logs/debug.jsonl | sort | uniq -c | sort -rn

# Average chunks kept after reranking
jq -s 'map(.reranking.chunks_kept) | add / length' logs/debug.jsonl

# Refusal reasons
jq -r 'select(.confidence_gate.decision == "refuse") | .confidence_gate.reason' logs/debug.jsonl
```

## Log Rotation

**Configuration:** `app/config.py`

```python
DEBUG_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEBUG_LOG_BACKUP_COUNT = 5               # Keep 5 backup files
```

**Files:**

```
logs/
├── debug.jsonl          # Current log
├── debug.jsonl.1        # Previous
├── debug.jsonl.2
├── debug.jsonl.3
├── debug.jsonl.4
└── debug.jsonl.5        # Oldest
```

When `debug.jsonl` exceeds 10 MB, it rotates to `debug.jsonl.1` and a new `debug.jsonl` starts.

## Performance Impact

**Debug mode adds minimal overhead:**

- Logging: ~1-2ms per query
- Disk I/O: Async (non-blocking)
- Memory: ~50 KB per query object

**Safe for production use** (logs can be analyzed post-hoc).

## Privacy Considerations

**Debug logs contain:**

- ✅ User queries (full text)
- ✅ Retrieved chunks (may be sensitive)
- ✅ LLM responses
- ✅ Timestamps
- ❌ No user IDs or PII (unless in query text)

**Security:**

- Store `logs/` directory securely
- Rotate/delete old logs per compliance requirements
- Consider encryption at rest for sensitive deployments

## Troubleshooting with Debug Mode

### "Why was my query refused?"

```bash
rag query --debug "Your question"

# Look for:
# Confidence gate: Decision: REFUSE
# Reason: [explanation]
```

### "Why is reranking dropping relevant chunks?"

```bash
rag query --debug "Your question"

# Look for:
# Reranking scores: [list of scores and explanations]
```

### "Why is search not finding the right chunks?"

```bash
rag query --debug "Your question"

# Look for:
# Retrieval: per_source_results
# Compare vector vs BM25 vs RRF results
```

### "Why is the answer using unexpected chunks?"

```bash
rag query --debug "Your question"

# Look for:
# Reranking: chunks_kept
# LLM: prompt (shows chunks sent to LLM)
```

### "How much is this costing me?"

```bash
rag query --debug "Your question"

# Look for:
# LLM: cost: $0.0278
```

## Best Practices

1. **Use for critical queries** - Verify system behavior on important questions
1. **Compare search modes** - Test vector vs keyword vs hybrid
1. **Monitor refusals** - Understand why queries are refused
1. **Track costs** - Analyze spending patterns
1. **Archive logs** - Keep for compliance/auditing

## Disabling Debug Logs

**To stop writing to `debug.jsonl` (keep stderr output):**

```python
# app/config.py
ENABLE_DEBUG_LOGGING = False  # (requires code change)
```

**To suppress all debug output:**

```bash
# Don't use --debug flag
rag query "What is a subscriber?"
```

## See Also

- [Audit Logging Guide](audit-logging.md) - Query audit logs (separate from debug)
- [Configuration Guide](configuration.md) - Log settings
- [Troubleshooting](../README.md#troubleshooting) - Common issues
- [Developer Guide](development/DEVELOPER_GUIDE.md) - Implementation details
