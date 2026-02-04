# Cost Estimation Guide

This document helps you estimate and manage OpenAI API costs for the License Intelligence System.

## Table of Contents

- [Overview](#overview)
- [Pricing Model](#pricing-model)
- [Cost Breakdown](#cost-breakdown)
- [Usage Estimation](#usage-estimation)
- [Cost Optimization](#cost-optimization)
- [Monitoring](#monitoring)

______________________________________________________________________

## Overview

The system uses OpenAI's API for two operations:

1. **Embeddings** (`text-embedding-3-large`) - During ingestion and query
1. **LLM** (`gpt-4.1`) - For reranking and answer generation

All costs are pay-as-you-go based on token usage.

______________________________________________________________________

## Pricing Model

### Current OpenAI Pricing (as of January 2026)

| Service                | Operation    | Cost per 1M tokens |
| ---------------------- | ------------ | ------------------ |
| text-embedding-3-large | Embedding    | $0.13              |
| gpt-4.1 (GPT-4 Turbo)  | Input        | $2.00              |
| gpt-4.1 (GPT-4 Turbo)  | Cached Input | $0.50              |
| gpt-4.1 (GPT-4 Turbo)  | Output       | $8.00              |

**Note:** Verify current pricing at [https://platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing)

______________________________________________________________________

## Cost Breakdown

### Ingestion Costs

**One-time cost** when loading documents:

```
Embedding Cost = (total_tokens / 1_000_000) × $0.13
```

**Example: CME dataset (~35 documents)**

- Total chunks: ~380
- Average tokens per chunk: ~600
- Total tokens: 380 × 600 = 228,000 tokens
- **Cost: $0.03**

**Scaling:**

- 100 documents ≈ 650,000 tokens ≈ **$0.08**
- 500 documents ≈ 3,250,000 tokens ≈ **$0.42**
- 1,000 documents ≈ 6,500,000 tokens ≈ **$0.85**

### Query Costs

Each query has three phases:

#### 1. Query Embedding

```
Cost = (query_tokens / 1_000_000) × $0.13
```

- Average query: ~15 tokens
- **Cost per query: $0.000002 (negligible)**

#### 2. Reranking (10 chunks)

**Based on actual usage (135 queries analyzed):**

```
Input Cost = (~2,500 tokens / 1_000_000) × $2.00 = $0.005
Output Cost = (~10 tokens / 1_000_000) × $8.00 = $0.00008
Total Reranking Cost ≈ $0.005 per query
```

**Why lower than expected?**

- Reranking uses efficient prompts (~250 tokens per chunk)
- With `RERANKING_INCLUDE_EXPLANATIONS = False` (default), output is 1 token per chunk
- Some queries retrieve fewer than 10 chunks

#### 3. Answer Generation

**Based on actual usage (135 queries analyzed):**

```
Average input tokens: ~2,500 (after reranking)
Average output tokens: ~700

Input Cost = (2,500 / 1_000_000) × $2.00 = $0.005
Output Cost = (700 / 1_000_000) × $8.00 = $0.0056
Total Answer Cost ≈ $0.011 per query
```

**Token usage breakdown (from logs):**

- Input tokens: Min: 900, Max: 9,800, Avg: 5,075 (total pipeline)
- Output tokens: Min: 40, Max: 1,900, Avg: 700
- Reranking uses ~2,500 tokens input
- Answer generation uses remaining ~2,500 tokens input

#### Total Query Cost

**Based on actual usage (135 queries):**

```
Query Embedding:     $0.000002 (negligible)
Reranking:           $0.005
Answer Generation:   $0.011
────────────────────────────
Total per query:     $0.016
```

**Cost per query: ~$0.02** (actual measured average)

**Note:** Costs vary by query complexity:

- Simple queries: ~$0.01 (fewer chunks, shorter answers)
- Complex queries: ~$0.03-0.04 (more chunks, detailed answers)

______________________________________________________________________

## Usage Estimation

### Monthly Cost Examples

#### Small Organization (100 queries/month)

```
Ingestion (one-time):  $0.08
Monthly queries:       100 × $0.02 = $2.00
────────────────────────────────────
First month:           $2.08
Subsequent months:     $2.00/month
```

#### Medium Organization (500 queries/month)

```
Ingestion (one-time):  $0.42
Monthly queries:       500 × $0.02 = $10.00
────────────────────────────────────
First month:           $10.42
Subsequent months:     $10.00/month
```

#### Large Organization (2,000 queries/month)

```
Ingestion (one-time):  $0.85
Monthly queries:       2,000 × $0.02 = $40.00
────────────────────────────────────
First month:           $40.85
Subsequent months:     $40.00/month
```

### Re-ingestion Costs

Re-ingestion is needed when:

- Adding new documents
- Updating existing documents
- Changing embedding models

**Incremental ingestion:**

Only new/modified documents are re-embedded, so costs are proportional to changes.

______________________________________________________________________

## Cost Optimization

### 1. Reduce Reranking Scope

**Default:**

```python
TOP_K_RETRIEVAL = 10  # Rerank 10 chunks
```

**Optimized:**

```python
TOP_K_RETRIEVAL = 5  # Rerank 5 chunks
```

**Savings:** ~50% on reranking costs ($0.0025 vs $0.005)

**Trade-off:** Slightly lower recall (may miss relevant chunks)

### 2. Disable Reranking Explanations (Already Default)

```python
RERANKING_INCLUDE_EXPLANATIONS = False
```

**Savings:** ~$0.005 per query (50% reduction in reranking output tokens)

### 3. Use Vector-Only Search for Simple Queries

```bash
rag query "What is CME?" --search-mode vector
```

**Savings:** Skips BM25 index building (minimal), but may reduce accuracy

### 4. Batch Queries

If you have multiple similar questions, consider:

- Consolidating into a single, well-formed question
- Using the API to batch process queries offline

### 5. Cache Common Queries

For frequently asked questions:

- Store answers in a simple key-value cache
- Serve from cache before calling the API
- Invalidate cache when documents are updated

**Example:** 20% cache hit rate saves ~$0.40/month on 100 queries

### 6. Monitor and Adjust

Use `logs/queries.jsonl` to track actual costs:

```bash
# Total tokens used this month
jq -r '[.tokens_input, .tokens_output] | @csv' logs/queries.jsonl | \
  awk -F, '{input+=$1; output+=$2} END {print "Input:", input, "Output:", output}'

# Average cost per query
jq -r '[.tokens_input * 2.00 / 1000000 + .tokens_output * 8.00 / 1000000] | @csv' logs/queries.jsonl | \
  awk -F, '{sum+=$1; count++} END {print "Avg cost per query: $" sum/count}'
```

______________________________________________________________________

## Monitoring

### Real-Time Monitoring

Enable query logging to stderr:

```bash
rag query "..." --log-queries
```

Output includes token counts:

```json
{
  "tokens_input": 10450,
  "tokens_output": 520
}
```

### Debug Mode Token Breakdown

```bash
rag query "..." --debug 2>&1 | jq '.final_context'
```

Shows:

- Chunk token count
- Definition token count
- Total tokens before LLM call

### Query Logs Analysis

Analyze `logs/queries.jsonl` for usage patterns:

```bash
# Queries per day
jq -r '.timestamp[:10]' logs/queries.jsonl | sort | uniq -c

# Average latency
jq -r '.latency_ms' logs/queries.jsonl | awk '{sum+=$1; count++} END {print sum/count " ms"}'

# Refusal rate
jq -r '.refused' logs/queries.jsonl | grep true | wc -l
```

### OpenAI Dashboard

Monitor usage and costs directly:

- [Usage Dashboard](https://platform.openai.com/usage)
- [API Key Limits](https://platform.openai.com/account/rate-limits)

______________________________________________________________________

## Cost Control Strategies

### Set OpenAI Usage Limits

1. Go to [https://platform.openai.com/account/limits](https://platform.openai.com/account/limits)
1. Set monthly budget cap
1. Enable email notifications at 75% and 100%

### Rate Limiting

For production deployments:

- Implement user rate limits (e.g., 10 queries/hour per user)
- Queue requests during peak usage
- Return cached results when possible

### Cost Alerts

Set up monitoring:

```bash
# Alert if daily cost exceeds threshold
jq -r '[.tokens_input * 2.00 / 1000000 + .tokens_output * 8.00 / 1000000]' logs/queries.jsonl | \
  awk '{sum+=$1} END {if (sum > 5.00) print "ALERT: Daily cost exceeded $5.00"}'
```

______________________________________________________________________

## Frequently Asked Questions

### Q: Why is GPT-4.1 so much more expensive than embeddings?

**A:** LLMs process more tokens (context + generation) and require more compute. Embeddings only encode text into vectors.

### Q: Can I use cheaper models?

**A:** OpenAI doesn't offer cheaper models with comparable quality. You could:

- Use `gpt-3.5-turbo` for reranking only (not recommended - accuracy drops)
- Disable reranking entirely (`--no-rerank` - not implemented, not recommended)

### Q: How much does it cost to re-ingest documents?

**A:** Same as initial ingestion - proportional to document count. Only re-ingest when documents change.

### Q: What if I exceed my OpenAI rate limit?

**A:** Upgrade to a higher tier:

- Tier 1: $5 spent → 500K TPM
- Tier 2: $50 spent → 2M TPM
- Tier 3: $1,000 spent → 10M TPM

See [https://platform.openai.com/docs/guides/rate-limits](https://platform.openai.com/docs/guides/rate-limits)

______________________________________________________________________

## Cost Comparison: Alternatives

### Local Models (Ollama)

**Pros:**

- No API costs
- No rate limits
- Data stays on-premises

**Cons:**

- Lower accuracy (~15-20% worse on legal/technical documents)
- Requires powerful hardware (32GB+ RAM for 8B models)
- Slower inference (~5-10x slower than GPT-4.1)

**Not recommended** for this system due to accuracy requirements.

### Claude or Other Providers

**Anthropic Claude:**

- Similar pricing to GPT-4
- Different strengths/weaknesses
- Not currently supported (OpenAI-only architecture)

______________________________________________________________________

## Related Documentation

- [Configuration Guide](configuration.md) - Adjust settings for cost optimization
- [Debug Mode](debug-mode.md) - Monitor token usage in real-time
- [Audit Logging](audit-logging.md) - Track usage over time
