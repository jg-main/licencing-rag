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
uv run python main.py query "What are the CME fees?"
```

#### Option B: Claude API - Fast, ~$0.003/query

```bash
# Set your API key (get one at https://console.anthropic.com/)
export ANTHROPIC_API_KEY="sk-ant-..."
export LLM_PROVIDER="anthropic"

# Run queries
uv run python main.py query "What are the CME fees?"
```

### Basic Usage

```bash
# Ingest documents
uv run python main.py ingest --provider cme

# Query the knowledge base
uv run python main.py query "What is a subscriber?"

# List indexed documents
uv run python main.py list --provider cme
```

## Configuration

Environment variables:

| Variable            | Default  | Description                           |
| ------------------- | -------- | ------------------------------------- |
| `LLM_PROVIDER`      | `ollama` | LLM provider: `ollama` or `anthropic` |
| `ANTHROPIC_API_KEY` | -        | Required for Claude API               |

Edit `app/config.py` for model selection and chunking parameters.

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
uv run python main.py ingest --provider cme
```

#### "Rate limit exceeded" (Claude API)

Too many requests. Wait a minute and try again, or upgrade your API plan.

#### Empty or poor extraction results

Some PDFs may be scanned images without text. Check the extraction:

```bash
# Enable debug logging to see extraction details
uv run python main.py --debug ingest --provider cme
```

### Debug Mode

Enable verbose logging with `--debug`:

```bash
uv run python main.py --debug query "What are the fees?"
```

### Getting Help

- Check the [RAG Tutorial](docs/rag-tutorial.md) for concepts
- Review [Implementation Plan](docs/implementation-plan.md) for architecture

## Documentation

- [RAG Tutorial](docs/rag-tutorial.md) - Beginner's guide to RAG
- [Implementation Plan](docs/implementation-plan.md) - Development roadmap
- [Specs v0.2](docs/specs.v0.2.md) - Technical specifications
