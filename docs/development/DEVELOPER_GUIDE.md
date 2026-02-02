# Developer Guide

**Version:** 0.4 (OpenAI Branch)\
**Last Updated:** January 30, 2026

This guide is for developers working on the License Intelligence System codebase.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Technical Specifications](#technical-specifications)
- [Implementation Phases](#implementation-phases)
- [Contributing](#contributing)

______________________________________________________________________

## Architecture Overview

### System Design

The system implements a Retrieval-Augmented Generation (RAG) pipeline with the following components:

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER QUERY                               │
└────────────────────────────┬────────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │ Normalization  │ (Remove filler words)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │   Embedding    │ (OpenAI text-embedding-3-large)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │ Hybrid Search  │ (Vector + BM25 → RRF)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │  LLM Reranking │ (GPT-4.1, 0-3 scoring)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │ Confidence Gate│ (Refuse if weak evidence)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │ Context Budget │ (Enforce ≤60k tokens)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │ Answer Gen     │ (GPT-4.1)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │   Validation   │ (Format check)
                    └────────┬───────┘
                             ↓
                    ┌────────────────┐
                    │  Audit Log     │ (logs/queries.jsonl)
                    └────────────────┘
```

### Technology Stack

| Component       | Technology             | Purpose                       |
| --------------- | ---------------------- | ----------------------------- |
| Runtime         | Python 3.13+           | Application runtime           |
| LLM             | GPT-4.1 (OpenAI)       | Answer generation + reranking |
| Embeddings      | text-embedding-3-large | 3072-dim vectors (OpenAI)     |
| Vector DB       | ChromaDB 1.4+          | Vector storage & search       |
| Keyword Search  | rank-bm25 0.2+         | BM25 keyword search           |
| PDF Extraction  | PyMuPDF 1.26+          | PDF text extraction           |
| DOCX Extraction | python-docx 1.2+       | DOCX text extraction          |
| Token Counting  | tiktoken 0.9+          | Accurate OpenAI token counts  |
| CLI Formatting  | Rich 14.0+             | Terminal output formatting    |
| Logging         | structlog 25.0+        | Structured logging            |

______________________________________________________________________

## Development Setup

### Prerequisites

- Python 3.13+
- OpenAI API key
- Git
- uv package manager (recommended) or pip

### Clone and Install

```bash
# Clone repository
git clone <repository-url>
cd licencing-rag

# Checkout openai branch
git checkout openai

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

### Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
```

### Verify Installation

```bash
# Run tests
pytest

# Run QA checks
make qa

# Check CLI
rag --help
```

______________________________________________________________________

## Project Structure

```
licencing-rag/
├── app/                    # Main application code
│   ├── audit.py           # Query audit logging
│   ├── budget.py          # Context budget enforcement
│   ├── chunking.py        # Document chunking
│   ├── cli.py             # CLI entry point
│   ├── config.py          # Configuration constants
│   ├── debug.py           # Debug logging
│   ├── definitions.py     # Definitions auto-linking
│   ├── embed.py           # OpenAI embeddings
│   ├── extract.py         # PDF/DOCX extraction
│   ├── gate.py            # Confidence gating
│   ├── ingest.py          # Document ingestion
│   ├── llm.py             # OpenAI LLM client
│   ├── logging.py         # Structured logging setup
│   ├── normalize.py       # Query normalization
│   ├── output.py          # Output formatting
│   ├── prompts.py         # LLM prompts
│   ├── query.py           # Query orchestration
│   ├── rerank.py          # LLM reranking
│   ├── search.py          # Hybrid search (vector + BM25)
│   └── validate.py        # Output validation
├── data/                  # Data storage
│   ├── raw/              # Source documents (PDF, DOCX, TXT)
│   │   └── cme/          # Organized by provider
│   ├── text/             # Extracted text files
│   └── chunks/           # Chunked documents (JSONL)
├── index/                # Search indices
│   ├── chroma/          # ChromaDB vector database
│   ├── bm25/            # BM25 keyword indices
│   └── definitions/     # Definitions indices
├── logs/                # Application logs
│   ├── debug.jsonl     # Debug pipeline logs
│   └── queries.jsonl   # Query audit logs
├── tests/              # Test suite
├── docs/               # Documentation
│   ├── configuration.md
│   ├── cost-estimation.md
│   ├── data-sources.md
│   ├── hybrid-search.md
│   ├── rag-tutorial.md
│   └── development/
│       ├── rag.specs.md
│       └── rag.implementation-plan.md
├── eval/               # Evaluation framework
│   ├── questions.json
│   ├── run_eval.py
│   └── results.json
├── pyproject.toml      # Project dependencies
├── Makefile            # Development tasks
└── README.md           # User documentation
```

______________________________________________________________________

## Development Workflow

### Making Changes

1. **Create a feature branch**

   ```bash
   git checkout -b feature/your-feature
   ```

1. **Make your changes**

   - Edit code in `app/`
   - Add tests in `tests/`
   - Update documentation as needed

1. **Run QA checks**

   ```bash
   make qa
   ```

1. **Run tests**

   ```bash
   pytest
   pytest --cov=app --cov-report=term-missing
   ```

1. **Commit with conventional commits**

   ```bash
   git add .
   git commit -m "feat(module): description"
   ```

   Format: `type(scope): description`

   Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pre-commit Hooks

Hooks run automatically on `git commit`:

- ruff (linting + formatting)
- isort (import sorting)
- trailing whitespace
- end-of-file fixer
- JSON/YAML/TOML validation
- mdformat (markdown formatting)

### Development Commands

```bash
# Run all QA checks
make qa

# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Format code
ruff format app/ tests/

# Lint code
ruff check app/ tests/

# Type check
mypy app/

# Clean build artifacts
make clean
```

______________________________________________________________________

## Testing

### Test Structure

Tests are organized by module:

```
tests/
├── test_audit.py           # Audit logging
├── test_budget.py          # Context budget
├── test_chunking.py        # Document chunking
├── test_definitions.py     # Definitions extraction
├── test_embed.py           # Embeddings
├── test_extract.py         # PDF/DOCX extraction
├── test_gate.py            # Confidence gating
├── test_ingest.py          # Ingestion pipeline
├── test_normalize.py       # Query normalization
├── test_output.py          # Output formatting
├── test_query.py           # Query orchestration
├── test_rerank.py          # LLM reranking
├── test_search.py          # Hybrid search
└── test_validate.py        # Output validation
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_chunking.py

# Specific test
pytest tests/test_chunking.py::TestChunking::test_basic_chunking

# With coverage
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Fast (skip slow tests)
pytest -m "not slow"
```

### Coverage Goals

- **Target:** 70% overall
- **Current:** 77% (exceeds target)
- **Core modules:** 90%+ coverage
- **Entry points:** 0% (cli.py, `__main__.py` - acceptable)

______________________________________________________________________

## Code Quality

### Code Style

- **Formatter:** ruff (replaces black)
- **Linter:** ruff (replaces flake8, pylint)
- **Import sorter:** isort
- **Type checker:** mypy

### Style Guidelines

1. **Type hints:** Required for function signatures
1. **Docstrings:** Required for public functions/classes
1. **Line length:** 120 characters (enforced by ruff)
1. **Imports:** One per line, sorted by isort
1. **Naming:**
   - Functions: `snake_case`
   - Classes: `PascalCase`
   - Constants: `UPPER_SNAKE_CASE`
   - Private: `_leading_underscore`

### Documentation

- Module-level docstrings explain purpose
- Function docstrings use Google style
- Include examples for complex functions
- Update docs/ when adding features

______________________________________________________________________

## Technical Specifications

### Current Specification

📄 **[rag.specs.md](development/rag.specs.md)** - Complete technical specification for the OpenAI branch

### Implementation Phases

📋 **[rag.implementation-plan.md](development/rag.implementation-plan.md)** - Detailed phase-by-phase development plan

**Phase Status:**

| Phase | Name                    | Status      |
| ----- | ----------------------- | ----------- |
| 1     | OpenAI Embeddings       | ✅ Complete |
| 2     | Query Normalization     | ✅ Complete |
| 3     | Hybrid Search           | ✅ Complete |
| 4     | LLM Reranking           | ✅ Complete |
| 5     | Context Budget          | ✅ Complete |
| 6     | Confidence Gating       | ✅ Complete |
| 7     | LLM Prompt Discipline   | ✅ Complete |
| 8     | Debug & Audit Logging   | ✅ Complete |
| 9     | Evaluation Framework    | ⚠️ Partial  |
| 10    | Cleanup & Documentation | ✅ Complete |

______________________________________________________________________

## Implementation Phases

### Overview

The system was developed in 10 phases, each building on the previous:

**Phase 1-2:** Foundation (embeddings, extraction, chunking, ingestion)\
**Phase 3:** Hybrid search (vector + BM25 + RRF)\
**Phase 4:** LLM reranking for relevance scoring\
**Phase 5:** Context budget enforcement (≤60k tokens)\
**Phase 6:** Confidence gating (code-enforced refusal)\
**Phase 7:** LLM prompt discipline (accuracy-first)\
**Phase 8:** Debug and audit logging\
**Phase 9:** Evaluation framework (chunk recall, refusal accuracy)\
**Phase 10:** Documentation and cleanup

See [rag.implementation-plan.md](development/rag.implementation-plan.md) for detailed breakdown.

______________________________________________________________________

## Contributing

### Pull Request Process

1. Create feature branch from `openai`
1. Make changes with tests
1. Run `make qa` and `pytest`
1. Commit with conventional commit messages
1. Push and create PR
1. Wait for CI checks (if configured)
1. Request review

### Code Review Guidelines

- All code must have tests
- QA checks must pass
- No decrease in coverage
- Documentation updated
- Conventional commit messages

### Adding New Features

1. **Design:** Document in specs if significant
1. **Test-driven:** Write tests first
1. **Implement:** Add code in `app/`
1. **Validate:** Run QA and tests
1. **Document:** Update docs/ and README
1. **Evaluate:** Add to eval/ if affects accuracy

______________________________________________________________________

## Debugging

### Debug Mode

Enable verbose pipeline logging:

```bash
rag query "..." --debug
```

Output appears on stderr and in `logs/debug.jsonl`.

### Common Issues

**Import errors:**

```bash
pip install -e .
```

**OpenAI rate limits:**

- Check [rate limits](https://platform.openai.com/account/rate-limits)
- Upgrade tier if needed

**Test failures:**

```bash
# Run failed test with verbose output
pytest -vv tests/test_module.py::test_name

# Debug with pdb
pytest --pdb tests/test_module.py::test_name
```

______________________________________________________________________

## Release Process

### Version Numbering

Format: `0.MAJOR.MINOR`

- **MAJOR:** Breaking changes or new phase completion
- **MINOR:** New features, bug fixes

Current: `0.4.0` (Phase 10 complete)

### Creating a Release

1. Update version in `pyproject.toml`
1. Update CHANGELOG (if exists)
1. Tag release: `git tag v0.4.0`
1. Push tags: `git push --tags`

______________________________________________________________________

## Resources

### Internal Documentation

- [Configuration Guide](../configuration.md)
- [Cost Estimation](../cost-estimation.md)
- [Data Sources](../data-sources.md)
- [Hybrid Search](../hybrid-search.md)
- [RAG Tutorial](../rag-tutorial.md)

### External References

- [OpenAI API Docs](https://platform.openai.com/docs)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [Python Packaging](https://packaging.python.org/)

______________________________________________________________________

## Support

For development questions:

1. Check this guide
1. Read source code docstrings
1. Check tests for examples
1. Open an issue on GitHub

______________________________________________________________________

**Last Updated:** January 30, 2026\
**Maintainers:** [Your Team]
