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

| Service                | Operation | Cost per 1M tokens |
| ---------------------- | --------- | ------------------ |
| text-embedding-3-large | Embedding | $0.13              |
| gpt-4.1 (GPT-4 Turbo)  | Input     | $2.50              |
| gpt-4.1 (GPT-4 Turbo)  | Output    | $10.00             |

**Note:** Verify current pricing at [https://openai.com/pricing](https://openai.com/pricing)

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

```
Input Cost = (10 chunks × ~600 tokens × 2 / 1_000_000) × $2.50
Output Cost = (10 chunks × 1 token / 1_000_000) × $10.00
Total Reranking Cost ≈ $0.03 per query
```

**Why `× 2` for input?**

- Chunk text (~600 tokens)
- Reranking prompt (~600 tokens)
- Total: ~1,200 tokens per chunk

**Optimization:**

With `RERANKING_INCLUDE_EXPLANATIONS = False` (default), output is 1 token per chunk instead of ~50, saving ~$0.005 per query.

#### 3. Answer Generation

```
Input Cost = (prompt_tokens / 1_000_000) × $2.50
Output Cost = (completion_tokens / 1_000_000) × $10.00
```

**Typical values:**

- Prompt: 8,000-12,000 tokens (system prompt + chunks + definitions)
- Completion: 400-800 tokens (answer + citations)

**Example calculation:**

- Prompt: 10,000 tokens → (10,000 / 1_000_000) × $2.50 = **$0.025**
- Completion: 500 tokens → (500 / 1_000_000) × $10.00 = **$0.005**
- **Total: $0.030 per answer**

#### Total Query Cost

```
Query Embedding:     $0.000002
Reranking:           $0.030
Answer Generation:   $0.030
────────────────────────────
Total per query:     $0.060
```

**Cost per query: ~$0.06**

______________________________________________________________________

## Usage Estimation

### Monthly Cost Examples

#### Small Organization (100 queries/month)

```
Ingestion (one-time):  $0.08
Monthly queries:       100 × $0.06 = $6.00
────────────────────────────────────
First month:           $6.08
Subsequent months:     $6.00/month
```

#### Medium Organization (500 queries/month)

```
Ingestion (one-time):  $0.42
Monthly queries:       500 × $0.06 = $30.00
────────────────────────────────────
First month:           $30.42
Subsequent months:     $30.00/month
```

#### Large Organization (2,000 queries/month)

```
Ingestion (one-time):  $0.85
Monthly queries:       2,000 × $0.06 = $120.00
────────────────────────────────────
First month:           $120.85
Subsequent months:     $120.00/month
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

**Savings:** ~50% on reranking costs ($0.015 vs $0.030)

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

**Example:** 20% cache hit rate saves ~$1.20/month on 100 queries

### 6. Monitor and Adjust

Use `logs/queries.jsonl` to track actual costs:

```bash
# Total tokens used this month
jq -r '[.tokens_input, .tokens_output] | @csv' logs/queries.jsonl | \
  awk -F, '{input+=$1; output+=$2} END {print "Input:", input, "Output:", output}'

# Average cost per query
jq -r '[.tokens_input * 2.50 / 1000000 + .tokens_output * 10.00 / 1000000] | @csv' logs/queries.jsonl | \
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
jq -r '[.tokens_input * 2.50 / 1000000 + .tokens_output * 10.00 / 1000000]' logs/queries.jsonl | \
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
