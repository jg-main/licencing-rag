# tests/test_e2e.py
"""End-to-end integration tests for ingest → query pipeline."""

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from app.chunking import Chunk, chunk_document
from app.config import CHROMA_DIR
from app.extract import extract_document
from app.ingest import chunks_to_chroma_format, get_collection_name
from app.query import format_context, query


def _sanitize_metadata(metadatas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove None values from metadata dicts (ChromaDB doesn't accept None)."""
    return [
        {k: v for k, v in meta.items() if v is not None}
        for meta in metadatas
    ]


class TestIngestQuerySmokeTest:
    """End-to-end smoke tests for retrieval and citation formatting."""

    @pytest.fixture
    def temp_chroma_dir(self, tmp_path: Path) -> Path:
        """Create a temporary ChromaDB directory."""
        return tmp_path / "chroma"

    @pytest.fixture
    def mock_llm_response(self) -> str:
        """Mock LLM response with proper formatting."""
        return """## Answer
Based on the CME Market Data Information Policies, real-time quote data requires a monthly fee of $500.

## Supporting Clauses
The fee schedule specifies that "Real-time Quotes" have a monthly fee of $500 and an annual fee of $5,000.

## Citations
- [CME] sample-agreement.docx, Pages 1

## Notes
Fee amounts are subject to change. Contact CME for current pricing."""

    def test_ingest_and_query_smoke_test(
        self, sample_docx: Path, temp_chroma_dir: Path, mock_llm_response: str
    ) -> None:
        """Full pipeline: extract → chunk → ingest → query → formatted response."""
        # 1. Extract document
        extracted = extract_document(sample_docx)
        assert extracted.word_count > 0, "Extraction should produce content"

        # 2. Chunk document
        chunks = chunk_document(extracted, "cme")
        assert len(chunks) > 0, "Chunking should produce at least one chunk"

        # Verify chunk metadata
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.provider == "cme"
            assert chunk.document_name == sample_docx.name

        # 3. Convert to ChromaDB format
        documents, metadatas, ids = chunks_to_chroma_format(chunks)
        assert len(documents) == len(chunks)
        assert len(metadatas) == len(chunks)
        assert len(ids) == len(chunks)

        # 4. Ingest into ChromaDB
        client = chromadb.PersistentClient(path=str(temp_chroma_dir))
        collection_name = get_collection_name("cme")

        # Use default embedding for test (no Ollama required)
        collection = client.get_or_create_collection(name=collection_name)
        collection.add(
            documents=documents,
            metadatas=_sanitize_metadata(metadatas),
            ids=ids,
        )

        # Verify ingestion
        assert collection.count() == len(chunks)

        # 5. Query the collection (raw retrieval, no LLM)
        results = collection.query(
            query_texts=["What is the fee for real-time quotes?"],
            n_results=3,
        )
        assert results["documents"] is not None
        assert len(results["documents"][0]) > 0, "Should retrieve at least one chunk"

        # 6. Format context for LLM
        context = format_context(
            results["documents"][0],
            results["metadatas"][0],  # type: ignore[arg-type]
        )
        assert "[CME]" in context, "Context should include provider prefix"
        assert "sample-agreement.docx" in context, "Context should include doc name"

    def test_citation_formatting(
        self, sample_docx: Path, temp_chroma_dir: Path, mock_llm_response: str
    ) -> None:
        """Verify citation format matches spec: [PROVIDER] doc_name, Pages X-Y."""
        # Extract and chunk
        extracted = extract_document(sample_docx)
        chunks = chunk_document(extracted, "cme")
        documents, metadatas, ids = chunks_to_chroma_format(chunks)

        # Ingest
        client = chromadb.PersistentClient(path=str(temp_chroma_dir))
        collection = client.get_or_create_collection(name=get_collection_name("cme"))
        collection.add(
            documents=documents,
            metadatas=_sanitize_metadata(metadatas),
            ids=ids,
        )

        # Query
        results = collection.query(
            query_texts=["What are the fee rates?"],
            n_results=2,
        )

        # Format context
        context = format_context(
            results["documents"][0],
            results["metadatas"][0],  # type: ignore[arg-type]
        )

        # Verify citation components present
        assert "[CME]" in context
        # Page number should be present (format may be "Page 1" or "Pages 1-2")
        import re

        page_match = re.search(r"Page\s+\d+", context)
        assert page_match is not None, f"Citation should include page number. Context: {context}"

    def test_full_query_with_mocked_llm(
        self, sample_docx: Path, temp_chroma_dir: Path, mock_llm_response: str
    ) -> None:
        """Full query pipeline with mocked LLM and ChromaDB client."""
        # Prepare documents
        extracted = extract_document(sample_docx)
        chunks = chunk_document(extracted, "cme")
        documents, metadatas, ids = chunks_to_chroma_format(chunks)
        sanitized_metadatas = _sanitize_metadata(metadatas)

        # Create a mock client that returns our collection
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [documents[:2]],
            "metadatas": [sanitized_metadatas[:2]],
            "ids": [ids[:2]],
            "distances": [[0.1, 0.2]],
        }

        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_collection

        # Mock LLM provider
        mock_provider = MagicMock()
        mock_provider.generate.return_value = mock_llm_response

        with (
            patch("app.query.CHROMA_DIR", temp_chroma_dir),
            patch("app.query.chromadb.PersistentClient", return_value=mock_client),
            patch("app.query.OllamaEmbeddingFunction"),
            patch("app.query.get_llm", return_value=mock_provider),
        ):
            # Ensure CHROMA_DIR exists for the check
            temp_chroma_dir.mkdir(parents=True, exist_ok=True)

            # Run query
            result = query("What is the fee for real-time quotes?", providers=["cme"])

            # Verify response structure
            assert "answer" in result
            assert "citations" in result
            assert "[CME]" in result["answer"]

            # Verify LLM was called
            mock_provider.generate.assert_called_once()
