# Licencing Retrieval-Augmented Generation

- Local RAG system for license agreements.
- Answers are grounded strictly in provided documents.
- No training. No cloud. No hallucinations (by design).

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.com/) (for local inference) OR Anthropic API key

### Installation

```bash
# Clone and install dependencies
git clone <repo-url>
cd licencing-rag
uv sync

# Install CLI entry point (enables 'rag' command)
pip install -e .

# Pull embedding model (required)
ollama pull nomic-embed-text
```

### Choose Your LLM Provider

#### Option A: Local (Ollama) - Free, requires RAM

```bash
# Pull a model
ollama pull llama3.2:3b   # For limited RAM (<8GB)
ollama pull llama3.1:8b   # For 8GB+ RAM

# Run queries (default provider)
rag query "What are the CME fees?"
```

#### Option B: Claude API - Fast, ~$0.003/query

```bash
# Set your API key (get one at https://console.anthropic.com/)
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"

# Run queries
rag query "What are the CME fees?"
```

### Basic Usage

```bash
# Ingest documents (supports subdirectories)
rag ingest --provider cme

# Query the knowledge base
rag query "What is a subscriber?"

# Query with JSON output
rag query --format json "What are the fees?" > result.json

# List indexed documents
rag list --provider cme

# View query logs
rag logs --tail 10

# Start REST API server (coming in Sprint 4)
rag serve --port 8000 --host 0.0.0.0
```

### Document Organization

Documents can be organized in subdirectories for better management:

```
data/raw/cme/
├── Fees/
│   ├── january-2025-market-data-fee-list.pdf
│   └── schedule-2-rates.pdf
└── Agreements/
    ├── information-license-agreement.pdf
    └── subscriber-terms.pdf
```

The system will recursively discover and process all documents while maintaining deterministic ordering.

## Configuration

Environment variables:

| Variable            | Default  | Description                           |
| ------------------- | -------- | ------------------------------------- |
| `LLM_PROVIDER`      | `ollama` | LLM provider: `ollama` or `anthropic` |
| `ANTHROPIC_API_KEY` | -        | Required for Claude API               |

Edit `app/config.py` for model selection and chunking parameters.

## Features

### Current (v0.3)
- ✅ **Multi-provider support** - Organize documents by data provider (CME, OPRA, etc.)
- ✅ **Subdirectory organization** - Nested folder structure for document management
- ✅ **Dual LLM support** - Claude API (fast) or Ollama (local, private)
- ✅ **Page-level citations** - Every answer includes exact document references
- ✅ **Grounded responses** - Explicit refusal when answer not in documents
- ✅ **Comprehensive testing** - 75 tests covering core functionality

### Coming Soon
- 🚧 **Hybrid search** (Sprint 3) - BM25 keyword + vector semantic search with RRF
- 🚧 **Definitions auto-linking** (Sprint 3) - Automatic definition retrieval for quoted terms
- 🚧 **Query logging** (Sprint 3) - JSONL audit logs for compliance
- 🚧 **Output formats** (Sprint 3) - Rich console formatting + JSON output
- 🚧 **REST API** (Sprint 4) - FastAPI with OpenAPI documentation
- 🚧 **AWS deployment** (Sprint 5) - Docker + ECS/Fargate with CI/CD

## Troubleshooting

### Common Issues

#### "Cannot connect to Ollama"

Ollama server is not running.

```bash
# Start Ollama
ollama serve

# Or on macOS, ensure the Ollama app is running
```

#### "Model not found" (Ollama)

The required model hasn't been downloaded.

```bash
# Pull embedding model (required)
ollama pull nomic-embed-text

# Pull LLM model
ollama pull llama3.2:8b
```

#### "ANTHROPIC_API_KEY environment variable is required"

Claude API key not configured.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"
```

#### "No index found"

Documents haven't been ingested yet.

```bash
rag ingest --provider cme
```

#### "Rate limit exceeded" (Claude API)

Too many requests. Wait a minute and try again, or upgrade your API plan.

#### Empty or poor extraction results

Some PDFs may be scanned images without text. Check the extraction:

```bash
# Enable debug logging to see extraction details
rag --debug ingest --provider cme
```

### Debug Mode

Enable verbose logging with `--debug`:

```bash
rag --debug query "What are the fees?"
```

### Getting Help

- Check the [RAG Tutorial](docs/rag-tutorial.md) for concepts
- Review [Implementation Plan](docs/implementation-plan.md) for architecture

## Documentation

- [RAG Tutorial](docs/rag-tutorial.md) - Beginner's guide to RAG
- [Implementation Plan](docs/implementation-plan.md) - Development roadmap
- [Specs v0.3](docs/specs.v0.3.md) - Technical specifications
- [Subdirectory Implementation](SUBDIRECTORY_IMPLEMENTATION.md) - Subdirectory support details
