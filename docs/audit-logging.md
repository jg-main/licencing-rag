# Audit Logging Guide

This guide explains how the system logs queries for compliance and analysis.

## Overview

Audit logging tracks every query for compliance, cost monitoring, and system analysis:

```
Every query → logs/queries.jsonl
```

**Separate from debug logs:**

- **Debug logs** (`logs/debug.jsonl`): Full pipeline details, verbose
- **Audit logs** (`logs/queries.jsonl`): Query summaries, compliance-focused

## What Is Logged

### Basic Information

- Query ID (unique identifier)
- Timestamp (ISO 8601 UTC)
- Original user question
- Normalized query (after preprocessing)
- Sources searched
- Answer provided (or refusal)

### Retrieval Metadata

- Search mode used (vector, keyword, hybrid)
- Number of chunks retrieved
- Number of chunks used in final answer
- Definitions auto-linked (if any)

### Cost Tracking

- Embedding tokens used
- LLM prompt tokens
- LLM completion tokens
- Total tokens
- Estimated cost ($USD)

### Performance

- Total query duration (milliseconds)
- Retrieval time
- Reranking time
- LLM time

### Refusals

- Whether query was refused
- Refusal reason (from confidence gate)
- Confidence scores

## Log Format

**File:** `logs/queries.jsonl` (one JSON object per line)

**Example entry:**

```json
{
  "query_id": "q_1738284730_abc123",
  "timestamp": "2026-01-30T15:45:30.123456Z",
  "query": {
    "original": "What is a subscriber?",
    "normalized": "subscriber",
    "sources": ["cme"],
    "search_mode": "hybrid"
  },
  "retrieval": {
    "chunks_retrieved": 10,
    "chunks_reranked": 3,
    "chunks_used": 3,
    "definitions_linked": 1
  },
  "answer": {
    "provided": true,
    "refused": false,
    "refusal_reason": null,
    "word_count": 45,
    "citation_count": 1
  },
  "cost": {
    "embedding_tokens": 3,
    "prompt_tokens": 2633,
    "completion_tokens": 145,
    "total_tokens": 2781,
    "estimated_cost_usd": 0.0278
  },
  "performance": {
    "total_ms": 1420,
    "retrieval_ms": 120,
    "reranking_ms": 850,
    "llm_ms": 380,
    "other_ms": 70
  },
  "metadata": {
    "embedding_model": "text-embedding-3-large",
    "llm_model": "gpt-4.1",
    "reranking_enabled": true,
    "confidence_gate_passed": true,
    "budget_enforced": true
  }
}
```

## Use Cases

### 1. Compliance Auditing

**Track who asked what and when:**

```bash
# All queries in date range
jq 'select(.timestamp >= "2026-01-30T00:00:00Z" and .timestamp <= "2026-01-31T00:00:00Z")' logs/queries.jsonl

# Export for compliance review
jq -s 'map({timestamp, query: .query.original, answer_provided: .answer.provided})' logs/queries.jsonl > audit_report.json
```

### 2. Cost Monitoring

**Track spending:**

```bash
# Total cost today
jq -s 'map(select(.timestamp | startswith("2026-01-30"))) | map(.cost.estimated_cost_usd) | add' logs/queries.jsonl

# Cost by source
jq -s 'group_by(.query.sources[0]) | map({source: .[0].query.sources[0], total_cost: map(.cost.estimated_cost_usd) | add})' logs/queries.jsonl

# Most expensive queries
jq -s 'sort_by(-.cost.estimated_cost_usd) | .[0:10]' logs/queries.jsonl
```

### 3. Usage Analysis

**Understand query patterns:**

```bash
# Most common queries
jq -r '.query.normalized' logs/queries.jsonl | sort | uniq -c | sort -rn | head -20

# Refusal rate
echo "Refused:" $(jq -s 'map(select(.answer.refused == true)) | length' logs/queries.jsonl)
echo "Answered:" $(jq -s 'map(select(.answer.refused == false)) | length' logs/queries.jsonl)

# Average query duration
jq -s 'map(.performance.total_ms) | add / length' logs/queries.jsonl
```

### 4. System Optimization

**Identify bottlenecks:**

```bash
# Average time by stage
jq -s '{
  avg_retrieval_ms: (map(.performance.retrieval_ms) | add / length),
  avg_reranking_ms: (map(.performance.reranking_ms) | add / length),
  avg_llm_ms: (map(.performance.llm_ms) | add / length)
}' logs/queries.jsonl

# Slowest queries
jq -s 'sort_by(-.performance.total_ms) | .[0:10] | map({query: .query.original, duration_ms: .performance.total_ms})' logs/queries.jsonl
```

### 5. Accuracy Monitoring

**Track refusal patterns:**

```bash
# Refusal reasons distribution
jq -r 'select(.answer.refused == true) | .answer.refusal_reason' logs/queries.jsonl | sort | uniq -c | sort -rn

# Low-confidence answers (passed gate but weak evidence)
jq 'select(.metadata.confidence_gate_passed == true and .retrieval.chunks_reranked < 2)' logs/queries.jsonl
```

## Log Rotation

**Configuration:** `app/config.py`

```python
AUDIT_LOG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
AUDIT_LOG_BACKUP_COUNT = 10              # Keep 10 backup files
```

**Files:**

```
logs/
├── queries.jsonl         # Current log
├── queries.jsonl.1       # Previous
├── queries.jsonl.2
├── ...
└── queries.jsonl.10      # Oldest
```

When `queries.jsonl` exceeds 50 MB, it rotates.

## Privacy & Security

### What's Logged

- ✅ User queries (full text)
- ✅ System responses
- ✅ Timestamps
- ❌ User IDs (not collected)
- ❌ IP addresses (not collected)
- ❌ Session data (not collected)

### Privacy Controls

**Disable logging (not recommended):**

```python
# app/config.py
ENABLE_AUDIT_LOGGING = False  # (requires code change)
```

**Redact sensitive queries:**

```python
# app/audit.py
def log_query(query, answer, metadata):
    # Example: Redact queries containing PII patterns
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', query):  # SSN
        query = "[REDACTED]"

    # ... normal logging ...
```

### Compliance

**For GDPR/CCPA compliance:**

1. **Data minimization** - Logs contain only necessary data
1. **Retention policy** - Rotate/delete logs per requirements
1. **Access controls** - Restrict `logs/` directory permissions
1. **Encryption** - Consider encryption at rest for sensitive data
1. **Right to erasure** - Manual deletion if needed

## Cost Estimates

**Log storage:**

- Average entry size: ~1 KB
- 1000 queries/day: ~1 MB/day, ~30 MB/month
- With rotation (10 files × 50 MB): ~500 MB max

**Analysis cost:** Free (local processing with `jq`)

## Analyzing Logs Programmatically

### Python Example

```python
import json
from pathlib import Path
from datetime import datetime

# Load all queries
queries = []
with open("logs/queries.jsonl") as f:
    for line in f:
        queries.append(json.loads(line))

# Total cost
total_cost = sum(q["cost"]["estimated_cost_usd"] for q in queries)
print(f"Total cost: ${total_cost:.2f}")

# Refusal rate
refusals = sum(1 for q in queries if q["answer"]["refused"])
print(f"Refusal rate: {refusals / len(queries) * 100:.1f}%")

# Average duration
avg_duration = sum(q["performance"]["total_ms"] for q in queries) / len(queries)
print(f"Average duration: {avg_duration:.0f} ms")
```

### SQL-Like Queries (with `jq`)

```bash
# SELECT query, cost FROM queries WHERE cost > 0.05 ORDER BY cost DESC
jq -s 'map(select(.cost.estimated_cost_usd > 0.05)) | sort_by(-.cost.estimated_cost_usd) | map({query: .query.original, cost: .cost.estimated_cost_usd})' logs/queries.jsonl

# SELECT AVG(total_ms) FROM queries GROUP BY search_mode
jq -s 'group_by(.query.search_mode) | map({mode: .[0].query.search_mode, avg_ms: (map(.performance.total_ms) | add / length)})' logs/queries.jsonl
```

## Alerting

### Set Up Alerts

**Example: Email alert on high refusal rate**

```bash
#!/bin/bash
# check_refusal_rate.sh

REFUSAL_RATE=$(jq -s 'map(select(.answer.refused == true)) | length / (map(.) | length) * 100' logs/queries.jsonl)

if (( $(echo "$REFUSAL_RATE > 20" | bc -l) )); then
    echo "High refusal rate: ${REFUSAL_RATE}%" | mail -s "RAG Alert" admin@example.com
fi
```

**Example: Slack alert on high cost**

```bash
#!/bin/bash
# check_daily_cost.sh

DAILY_COST=$(jq -s "map(select(.timestamp | startswith(\"$(date -u +%Y-%m-%d)\"))) | map(.cost.estimated_cost_usd) | add" logs/queries.jsonl)

if (( $(echo "$DAILY_COST > 100" | bc -l) )); then
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"RAG daily cost exceeded $100: \$$DAILY_COST\"}" \
        $SLACK_WEBHOOK_URL
fi
```

## Best Practices

1. **Regular review** - Check logs weekly for anomalies
1. **Cost tracking** - Monitor spending trends
1. **Refusal analysis** - Investigate high refusal rates
1. **Performance monitoring** - Track query latency
1. **Archive old logs** - Compress/delete per retention policy
1. **Secure storage** - Restrict access to logs directory
1. **Backup logs** - Include in backup strategy

## Viewing Logs

### Real-Time Monitoring

```bash
# Tail logs (follow mode)
tail -f logs/queries.jsonl | jq .

# Watch refusals in real-time
tail -f logs/queries.jsonl | jq 'select(.answer.refused == true)'
```

### Summary Reports

```bash
# Daily summary
cat logs/queries.jsonl | jq -s "
map(select(.timestamp | startswith(\"$(date -u +%Y-%m-%d)\"))) | {
  total_queries: length,
  refusals: map(select(.answer.refused == true)) | length,
  total_cost: map(.cost.estimated_cost_usd) | add,
  avg_duration_ms: map(.performance.total_ms) | add / length
}"

# Weekly summary
cat logs/queries.jsonl | jq -s "
map(select(.timestamp | startswith(\"$(date -u -d '7 days ago' +%Y-%m)\"))) | {
  total_queries: length,
  total_cost: map(.cost.estimated_cost_usd) | add,
  unique_questions: map(.query.normalized) | unique | length
}"
```

## Disabling Audit Logging

**Not recommended for production**, but possible:

```python
# app/config.py
ENABLE_AUDIT_LOGGING = False  # Disables query logging
```

**Effect:** No queries logged to `queries.jsonl`. Compliance and cost tracking unavailable.

## See Also

- [Debug Mode Guide](debug-mode.md) - Verbose pipeline logging
- [Configuration Guide](configuration.md) - Logging settings
- [Cost Estimation](cost-estimation.md) - Understanding costs
- [Developer Guide](development/DEVELOPER_GUIDE.md) - Implementation details
