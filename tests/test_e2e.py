# tests/test_e2e.py
"""End-to-end integration tests for ingest → query pipeline."""

import shutil
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from app.chunking import Chunk, chunk_document
from app.config import CHROMA_DIR
from app.extract import extract_document
from app.ingest import chunks_to_chroma_format, get_collection_name
from app.query import format_context, query


def _sanitize_metadata(
    metadatas: list[dict[str, Any]],
) -> list[dict[str, str | int | float | bool]]:
    """Remove None values from metadata dicts (ChromaDB doesn't accept None)."""
    return [
        {k: v for k, v in meta.items() if v is not None}
        for meta in metadatas
    ]  # type: ignore[return-value]


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
            metadatas=_sanitize_metadata(metadatas),  # type: ignore[arg-type]
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
        docs = results["documents"]
        metas = results["metadatas"]
        assert docs is not None and metas is not None
        context = format_context(
            docs[0],
            cast(list[dict[str, Any]], metas[0]),
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
            metadatas=_sanitize_metadata(metadatas),  # type: ignore[arg-type]
            ids=ids,
        )

        # Query
        results = collection.query(
            query_texts=["What are the fee rates?"],
            n_results=2,
        )

        # Format context
        docs = results["documents"]
        metas = results["metadatas"]
        assert docs is not None and metas is not None
        context = format_context(
            docs[0],
            cast(list[dict[str, Any]], metas[0]),
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


class TestHybridSearchE2E:
    """End-to-end tests for hybrid search with BM25 persistence and RRF."""

    @pytest.fixture
    def temp_bm25_dir(self, tmp_path: Path) -> Path:
        """Create temporary BM25 index directory."""
        bm25_dir = tmp_path / "bm25"
        bm25_dir.mkdir(parents=True, exist_ok=True)
        return bm25_dir

    @pytest.fixture
    def sample_documents(self) -> list[tuple[str, str]]:
        """Sample documents for BM25 indexing."""
        return [
            ("chunk_fee_1", "The fee schedule outlines real-time data fees at $100 per month"),
            ("chunk_fee_2", "Delayed data has reduced fees of $50 per month for subscribers"),
            ("chunk_redistribution", "Redistribution requires prior written approval from CME Group"),
            ("chunk_subscriber", "A Subscriber is defined as any person receiving market data"),
            ("chunk_general", "CME Group provides market data through various distribution channels"),
        ]

    def test_bm25_save_load_roundtrip(
        self, temp_bm25_dir: Path, sample_documents: list[tuple[str, str]]
    ) -> None:
        """Verify BM25 index can be saved, loaded, and queried correctly."""
        import app.search as search_module
        from app.search import BM25Index

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = temp_bm25_dir

        try:
            # Build and save index
            index = BM25Index("test_provider")
            chunk_ids = [doc[0] for doc in sample_documents]
            documents = [doc[1] for doc in sample_documents]
            index.add_documents(chunk_ids, documents)
            index.build()
            index.save()

            # Verify file exists
            index_path = temp_bm25_dir / "test_provider_index.pkl"
            assert index_path.exists()

            # Load and verify
            loaded = BM25Index.load("test_provider")
            assert loaded is not None
            assert len(loaded.chunk_ids) == len(sample_documents)

            # Query should find fee-related documents
            results = loaded.query("fee schedule real-time data", top_k=3)
            assert len(results) >= 1
            # First result should be the fee schedule chunk
            assert results[0][0] == "chunk_fee_1"

        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_hybrid_search_with_loaded_bm25(
        self, temp_bm25_dir: Path, tmp_path: Path, sample_documents: list[tuple[str, str]]
    ) -> None:
        """Test hybrid search combining vector results with loaded BM25 index."""
        import app.search as search_module
        from app.search import BM25Index, HybridSearcher, SearchMode

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = temp_bm25_dir

        try:
            # Build and save BM25 index
            index = BM25Index("test_provider")
            chunk_ids = [doc[0] for doc in sample_documents]
            documents = [doc[1] for doc in sample_documents]
            index.add_documents(chunk_ids, documents)
            index.build()
            index.save()

            # Load BM25 index (simulates fresh session)
            loaded_bm25 = BM25Index.load("test_provider")
            assert loaded_bm25 is not None

            # Create mock ChromaDB collection with vector search results
            # Vector search returns different ranking than BM25
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["chunk_general", "chunk_subscriber", "chunk_fee_2"]],
                "documents": [[
                    sample_documents[4][1],  # general (vector thinks this is relevant)
                    sample_documents[3][1],  # subscriber
                    sample_documents[1][1],  # fee_2
                ]],
                "metadatas": [[
                    {"chunk_id": "chunk_general", "provider": "test"},
                    {"chunk_id": "chunk_subscriber", "provider": "test"},
                    {"chunk_id": "chunk_fee_2", "provider": "test"},
                ]],
                "distances": [[0.1, 0.2, 0.3]],
            }
            mock_collection.get.return_value = {
                "ids": ["chunk_fee_1"],
                "documents": [sample_documents[0][1]],
                "metadatas": [{"chunk_id": "chunk_fee_1", "provider": "test"}],
            }

            # Run hybrid search
            searcher = HybridSearcher("test_provider", mock_collection, loaded_bm25)
            results = searcher.search("fee schedule real-time", mode=SearchMode.HYBRID, top_k=3)

            # Verify results
            assert len(results) >= 1

            # RRF should boost chunk_fee_1 because BM25 ranks it first for "fee schedule"
            # even though vector search didn't return it in top 3
            result_ids = [r.chunk_id for r in results]

            # chunk_fee_1 should appear because BM25 ranked it #1 and it was fetched
            # via collection.get() in the hybrid search
            assert "chunk_fee_1" in result_ids

            # Verify source is "hybrid"
            assert all(r.source == "hybrid" for r in results)

        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_hybrid_fallback_when_bm25_missing(
        self, temp_bm25_dir: Path, sample_documents: list[tuple[str, str]]
    ) -> None:
        """Hybrid search falls back to vector-only when BM25 index is missing."""
        import app.search as search_module
        from app.search import HybridSearcher, SearchMode

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = temp_bm25_dir

        try:
            # NO BM25 index saved - directory is empty

            # Create mock ChromaDB collection
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["chunk_1", "chunk_2"]],
                "documents": [[sample_documents[0][1], sample_documents[1][1]]],
                "metadatas": [[
                    {"chunk_id": "chunk_1", "provider": "test"},
                    {"chunk_id": "chunk_2", "provider": "test"},
                ]],
                "distances": [[0.1, 0.2]],
            }

            # Run hybrid search with no BM25 index
            searcher = HybridSearcher("test_provider", mock_collection, bm25_index=None)
            results = searcher.search("fee schedule", mode=SearchMode.HYBRID, top_k=2)

            # Should fall back to vector results
            assert len(results) == 2
            # Source should be "vector" since we fell back
            assert all(r.source == "vector" for r in results)

        finally:
            search_module.BM25_INDEX_DIR = original_dir
