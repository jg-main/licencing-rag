# RAG - License Intelligence System

**Version:** 0.4\
**Status:** Production Ready

A high-precision legal research tool that answers questions exclusively from market data license agreements using Retrieval-Augmented Generation (RAG). Powered by OpenAI for maximum accuracy.

______________________________________________________________________

## What Is This?

A **grounded legal analysis system** that:

- ✅ Answers questions **only** from uploaded license documents
- ✅ Explicitly refuses to answer when documents are silent
- ✅ Provides exact **citations** (source, document, section, page)
- ✅ Supports multiple data providers (CME, OPRA, CTA/UTP)
- ✅ Uses OpenAI GPT-4.1 for industry-leading accuracy
- ❌ **Not** a general chatbot
- ❌ **Not** a trained LLM that makes assumptions

### Supported Data Providers

| Provider  | Status     | Documents | Priority |
| --------- | ---------- | --------- | -------- |
| CME Group | ✅ Active  | ~44       | P0       |
| OPRA      | ⏳ Planned | TBD       | P1       |
| CTA/UTP   | ⏳ Planned | TBD       | P2       |

📋 **[View all data sources →](docs/data-sources.md)**

______________________________________________________________________

## Quick Start

### Installation

```bash
# 1. Clone repository
git clone <repo-url>
cd licencing-rag

# 2. Install dependencies (requires Python 3.13+)
pip install uv  # Fast package manager
uv sync
pip install -e .

# 3. Set OpenAI API key
export OPENAI_API_KEY="sk-..."  # Get from platform.openai.com
```

### Basic Usage

```bash
# Load documents
rag ingest --source cme

# Ask questions
rag query "What is a subscriber?"
rag query "What are the redistribution fees?"

# View indexed documents
rag list --source cme
```

**Cost:** ~$0.03 per query (~$90/month for 100 queries/day)

📖 **[See cost breakdown →](docs/cost-estimation.md)**

______________________________________________________________________

## Features

### Core Capabilities

- **TXT, PDF & DOCX Support** - Automatic text extraction with page tracking
- **Multi-Provider** - Organize documents by data source (CME, OPRA, etc.)
- **Hybrid Search** - Combines semantic (vector) and keyword (BM25) search
- **Auto-Linking** - Automatically retrieves definitions when terms appear
- **Accurate Refusals** - Explicitly states when answer is not in documents
- **Rich Citations** - Every answer includes document references

### Advanced Features

- **LLM Reranking** - GPT-4.1 scores chunks for relevance (0-3 scale)
- **Confidence Gating** - Code-enforced refusal when evidence is weak
- **Context Budget** - Enforces ≤60k token limit for LLM context
- **Query Normalization** - Removes filler words for better search
- **Debug Mode** - Full pipeline transparency for accuracy verification
- **Audit Logging** - Query tracking for compliance

### Output Formats

- **Console** - Rich formatted output with panels and tables (default)
- **JSON** - Structured data for programmatic access

______________________________________________________________________

## Installation

### Prerequisites

- **Python 3.13+**
- **OpenAI API key** - [Sign up here](https://platform.openai.com/)
- **uv package manager** - [Install guide](https://docs.astral.sh/uv/)

### Step-by-Step Setup

```bash
# 1. Clone and navigate
git clone <repo-url>
cd licencing-rag

# 2. Install dependencies
uv sync
pip install -e .

# 3. Configure API key
export OPENAI_API_KEY="sk-..."

# 4. Verify installation
rag --help
```

### First-Time Setup

```bash
# Delete any old incompatible indexes
make clean-all

# Ingest your first documents
mkdir -p data/raw/cme
# (Copy your PDFs to data/raw/cme/)
rag ingest --source cme

# Test with a query
rag query "What are the fees?"
```

______________________________________________________________________

## Usage

### Document Management

#### Organizing Documents

```
data/raw/
└── cme/                    # Provider name
    ├── Fees/               # Optional subdirectories
    │   ├── january-2025-fee-list.pdf
    │   └── schedule-a.pdf
    └── Agreements/
        ├── main-agreement.pdf
        └── subscriber-terms.pdf
```

**Supported formats:** PDF (text-based), DOCX, TXT

❌ **Not supported:** Scanned PDFs (OCR not included)

#### Loading Documents

```bash
# Ingest all documents for a provider
rag ingest --source cme

# View indexed documents
rag list --source cme

# View all sources
rag list
```

**What happens during ingestion:**

1. Scans `data/raw/{source}/` recursively for PDF/DOCX files
1. Extracts text with page tracking
1. Chunks documents (500-800 words, section-aware)
1. Generates embeddings via OpenAI (3072 dimensions)
1. Stores in ChromaDB vector database
1. Builds BM25 keyword index

### Querying

#### Basic Queries

```bash
# Simple question
rag query "What is a subscriber?"

# Question about fees
rag query "What are the CME redistribution fees?"

# Multi-part question
rag query "What are the requirements and fees for non-display use?"
```

#### Advanced Options

```bash
# Query specific source
rag query --source cme "What are the fees?"

# Query multiple sources
rag query --source cme --source opra "What is a subscriber?"

# JSON output for automation
rag query --format json "What are the fees?" > result.json

# Search modes
rag query --search-mode vector "..."    # Vector-only (semantic)
rag query --search-mode keyword "..."   # Keyword-only (BM25)
rag query --search-mode hybrid "..."    # Both (default, recommended)

# Debug mode (see pipeline details)
rag query --debug "What are the fees?"
```

#### Understanding Answers

**Console Output:**

```
╭─── Answer ────────────────────────────────────────────╮
│ The subscriber fee is $100 per month according to     │
│ Schedule A Section 3.1.                               │
╰───────────────────────────────────────────────────────╯

╭─── Supporting Clauses ────────────────────────────────╮
│ "Monthly fees for subscriber access shall be $100    │
│ per individual subscriber..."                         │
│                                                        │
│ Source: cme                                           │
│ Document: Fees/Schedule-A.pdf                         │
│ Section: Section 3.1 Pricing                          │
│ Pages: 5                                              │
╰───────────────────────────────────────────────────────╯

╭─── Definitions ───────────────────────────────────────╮
│ Subscriber: "Any individual authorized to receive     │
│ market data under a license agreement..."             │
│                                                        │
│ Source: cme                                           │
│ Document: Agreements/Main-Agreement.pdf               │
│ Section: Definitions                                  │
│ Pages: 2                                              │
╰───────────────────────────────────────────────────────╯
```

**JSON Output Structure:**

```json
{
  "answer": "The subscriber fee is $100 per month...",
  "supporting_clauses": [
    {
      "text": "Clause text from document...",
      "source": {
        "source": "cme",
        "document": "Fees/Schedule-A.pdf",
        "section": "Section 3.1 Pricing",
        "page_start": 5,
        "page_end": 5
      }
    }
  ],
  "definitions": [
    {
      "term": "Subscriber",
      "definition": "\"Subscriber\" means any individual...",
      "source": { /* ... */ }
    }
  ],
  "citations": [ /* ... */ ],
  "metadata": {
    "sources": ["cme"],
    "chunks_retrieved": 5,
    "search_mode": "hybrid",
    "timestamp": "2026-01-27T10:30:00+00:00"
  }
}
```

### Configuration

#### Environment Variables

| Variable         | Required | Default        | Description         |
| ---------------- | -------- | -------------- | ------------------- |
| `OPENAI_API_KEY` | Yes      | -              | OpenAI API key      |
| `CHROMA_DIR`     | No       | `index/chroma` | Vector DB directory |

#### REST API Configuration

For deploying the REST API, additional environment variables are required:

| Variable                  | Required | Default | Description                          |
| ------------------------- | -------- | ------- | ------------------------------------ |
| `RAG_API_KEY`             | Yes\*    | -       | API key for `/query` and `/sources`  |
| `SLACK_SIGNING_SECRET`    | Yes\*    | -       | Slack app signing secret             |
| `RAG_RATE_LIMIT`          | No       | `100`   | Max requests per minute per API key  |
| `RAG_CORS_ORIGINS`        | No       | (none)  | Comma-separated allowed origins      |
| `RAG_TRUST_PROXY_HEADERS` | No       | `false` | Trust X-Forwarded-For (behind proxy) |

\* Required when running the REST API

See [`.env.example`](.env.example) for a complete configuration template.

📖 **[Deployment guide →](docs/development/deployment-specs.md)**

#### Advanced Settings

Edit `app/config.py` to customize:

```python
# Models
EMBEDDING_MODEL = "text-embedding-3-large"  # OpenAI embeddings
LLM_MODEL = "gpt-4.1"                       # Answer generation

# Chunking
CHUNK_SIZE = 500          # Target words per chunk
CHUNK_OVERLAP = 100       # Overlap between chunks
MIN_CHUNK_SIZE = 100      # Minimum viable chunk

# Search
TOP_K = 10                # Chunks to retrieve
DEFAULT_SEARCH_MODE = "hybrid"  # vector, keyword, or hybrid

# Budget
MAX_CONTEXT_TOKENS = 60000  # Max tokens for LLM context
```

📖 **[Complete configuration guide →](docs/configuration.md)**

______________________________________________________________________

## How It Works

### Query Pipeline

```
User Question
    ↓
Query Normalization (remove filler words)
    ↓
Embedding (OpenAI text-embedding-3-large)
    ↓
Hybrid Search (Vector + BM25 → RRF)
    ↓
LLM Reranking (GPT-4.1, 0-3 relevance scoring)
    ↓
Confidence Gate (refuse if evidence weak)
    ↓
Context Budget (enforce ≤60k tokens)
    ↓
Answer Generation (GPT-4.1)
    ↓
Validation (format check)
    ↓
Audit Log (logs/queries.jsonl)
    ↓
Answer + Citations
```

### Key Technologies

| Component      | Technology             | Purpose           |
| -------------- | ---------------------- | ----------------- |
| LLM            | GPT-4.1 (OpenAI)       | Answer generation |
| Embeddings     | text-embedding-3-large | 3072-dim vectors  |
| Vector DB      | ChromaDB               | Semantic search   |
| Keyword Search | BM25                   | Keyword matching  |
| PDF Extract    | PyMuPDF                | Text extraction   |
| DOCX Extract   | python-docx            | DOCX parsing      |

### Why Hybrid Search?

**Vector search** (semantic): Understands meaning, not just keywords\
**Keyword search** (BM25): Finds exact terms, acronyms, numbers\
**Hybrid (RRF)**: Combines both for maximum recall and precision

📖 **[Learn more about hybrid search →](docs/hybrid-search.md)**

______________________________________________________________________

## Workflow Examples

### Initial Setup

```bash
# 1. Install system
uv sync && pip install -e .

# 2. Configure API
export OPENAI_API_KEY="sk-..."

# 3. Add documents
mkdir -p data/raw/cme/Fees
cp my-fee-schedule.pdf data/raw/cme/Fees/

# 4. Ingest
rag ingest --source cme

# 5. Query
rag query "What are the fees?"
```

### Regular Use

```bash
# Ask question
rag query "What is a non-display use?"

# Get JSON for automation
rag query --format json "What are subscriber requirements?" | jq .

# Debug pipeline
rag query --debug "What are redistribution fees?"
```

### Adding New Documents

```bash
# 1. Copy files to data/raw/{source}/
cp new-agreement.pdf data/raw/cme/Agreements/

# 2. Re-ingest (updates index)
rag ingest --source cme

# 3. Query new content
rag query "What does the new agreement say about fees?"
```

### Multiple Providers

```bash
# Set up new provider
mkdir -p data/raw/opra
cp opra-docs/*.pdf data/raw/opra/

# Ingest new provider
rag ingest --source opra

# Query specific provider
rag query --source opra "What are OPRA fees?"

# Query all providers
rag query "What are subscriber fees across all providers?"
```

______________________________________________________________________

## Limitations & Risks

### Known Limitations

1. **Text-based PDFs only** - No OCR for scanned documents
1. **English only** - No multilingual support
1. **No real-time updates** - Must re-ingest for document changes
1. **API dependency** - Requires OpenAI API access (internet + billing)
1. **Token limits** - Very long documents may exceed context budget
1. **No legal advice** - System provides information, not counsel

### Accuracy Considerations

- **Source quality matters** - Garbage in, garbage out
- **Context limits** - May miss relevant info in extremely long documents
- **Hallucination risk** - LLM may occasionally misinterpret chunks
- **Always verify** - Cross-check critical answers with source documents

### Operational Risks

- **Cost exposure** - OpenAI API charges per token (monitor usage)
- **Rate limits** - May hit API limits with heavy usage
- **Data privacy** - OpenAI processes your queries (review their terms)
- **Single point of failure** - System depends on OpenAI availability

### Best Practices

1. **Use debug mode** for critical queries (`--debug`)
1. **Verify citations** by checking source documents
1. **Monitor costs** with OpenAI dashboard
1. **Keep documents updated** via regular re-ingestion
1. **Test evaluation set** after major changes

📊 **[View evaluation results →](eval/results.json)**

______________________________________________________________________

## Troubleshooting

### Common Issues

#### "OPENAI_API_KEY environment variable is required"

```bash
# Solution: Set your API key
export OPENAI_API_KEY="sk-..."
```

Get a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

#### "No index found" or "Collection not found"

```bash
# Solution: Ingest documents first
rag ingest --source cme
```

#### "Rate limit exceeded"

**Problem:** Too many OpenAI API requests

**Solutions:**

- Wait 60 seconds and retry
- Upgrade API tier at [platform.openai.com/account/rate-limits](https://platform.openai.com/account/rate-limits)
- Reduce `TOP_K` in config to retrieve fewer chunks

#### Empty or poor extraction results

**Problem:** PDF may be scanned (no text layer)

```bash
# Check extracted text
cat data/text/cme/your-document.pdf.txt

# If empty, document is scanned (OCR not supported)
```

#### Embedding model mismatch

**Problem:** Index built with different model

```bash
# Solution: Delete old index and re-ingest
make clean-all
rag ingest --source cme
```

### Debug Mode

See exactly what's happening:

```bash
# Enable verbose logging
rag query --debug "What are the fees?"

# Debug output shows:
# - Query normalization
# - Embedding generation
# - Hybrid search results
# - Reranking scores
# - Confidence gate decision
# - Token usage
# - LLM prompt and response
```

Output appears on stderr and in `logs/debug.jsonl` (machine-parsable).

### Getting Help

1. **Check documentation:** See [Documentation](#documentation) section
1. **Review logs:** `logs/debug.jsonl` and `logs/queries.jsonl`
1. **Open issue:** [GitHub Issues](https://github.com/your-repo/issues)

______________________________________________________________________

## Documentation

### User Guides

- **[Configuration Guide](docs/configuration.md)** - All settings explained
- **[Cost Estimation](docs/cost-estimation.md)** - Pricing and optimization
- **[Data Sources](docs/data-sources.md)** - Provider document tracking
- **[Hybrid Search](docs/hybrid-search.md)** - How search works
- **[RAG Tutorial](docs/rag-tutorial.md)** - Beginner's guide to RAG

### Developer Resources

- **[Developer Guide](docs/development/DEVELOPER_GUIDE.md)** - Architecture and development
- **[Technical Specs](docs/development/rag.specs.md)** - Complete specification
- **[Implementation Plan](docs/development/rag.implementation-plan.md)** - Development roadmap

### Component Guides

- **Query Normalization** - See `app/normalize.py` docstrings
- **Reranking** - See `app/rerank.py` docstrings
- **Confidence Gating** - See `app/gate.py` docstrings
- **Context Budget** - See `app/budget.py` docstrings
- **Debug Mode** - See `app/debug.py` docstrings
- **Audit Logging** - See `app/audit.py` docstrings

______________________________________________________________________

## Cost Management

### Pricing Overview

**Per Query (typical):** ~$0.03\
**100 queries/day:** ~$90/month\
**500 queries/day:** ~$450/month

### Cost Breakdown

| Operation | Model                  | Cost per Query |
| --------- | ---------------------- | -------------- |
| Embedding | text-embedding-3-large | ~$0.002        |
| Reranking | gpt-4.1                | ~$0.015        |
| Answer    | gpt-4.1                | ~$0.015        |

### Optimization Tips

1. **Use vector-only search** - Skip BM25 for faster queries
1. **Reduce TOP_K** - Retrieve fewer chunks (costs scale linearly)
1. **Monitor with debug** - `--debug` shows token usage
1. **Batch ingestion** - Re-ingest only changed documents
1. **Use caching** - Definitions are cached automatically

📖 **[Complete cost guide →](docs/cost-estimation.md)**

______________________________________________________________________

## Performance

### Benchmarks

**Ingestion:** ~50 documents in ~5 minutes (depends on doc size)\
**Query:** 1-3 seconds typical (depends on chunk count and LLM response time)\
**Accuracy:** 87.5% chunk recall on evaluation set

### Evaluation Results

| Metric           | Score | Target |
| ---------------- | ----- | ------ |
| Chunk Recall     | 87.5% | ≥75%   |
| Refusal Accuracy | 100%  | 100%   |
| False Refusal    | 0%    | 0%     |
| False Acceptance | 0%    | 0%     |

📊 **[View full results →](eval/results.json)**

______________________________________________________________________

## Development

### For Contributors

If you want to extend or modify the system:

```bash
# Install with dev dependencies
uv sync
pip install -e ".[dev]"

# Run tests
pytest

# Run quality checks
make qa

# Format code
make format
```

📖 **[Full developer guide →](docs/development/DEVELOPER_GUIDE.md)**

### Project Structure

```
licencing-rag/
├── app/            # Application code
├── data/           # Documents and processing artifacts
├── index/          # Search indices (ChromaDB, BM25)
├── logs/           # Query and debug logs
├── tests/          # Test suite (77% coverage)
├── eval/           # Evaluation framework
└── docs/           # Documentation
```

______________________________________________________________________

## Support

### Getting Help

- **Documentation:** See [Documentation](#documentation) section
- **Issues:** [Open a GitHub issue](https://github.com/your-repo/issues)
- **Questions:** Check existing issues or create new one

### Reporting Bugs

Include:

1. Command you ran
1. Error message
1. Debug output (`--debug` flag)
1. OpenAI model versions (in `app/config.py`)

______________________________________________________________________

**Last Updated:** January 30, 2026\
**Version:** 0.4 (Production Ready)
