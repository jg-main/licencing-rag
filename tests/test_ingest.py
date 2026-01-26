# tests/test_ingest.py
"""Tests for document ingestion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.chunking import Chunk
from app.ingest import chunks_to_chroma_format, get_collection_name


class TestChunksToChromaFormat:
    """Tests for converting chunks to ChromaDB format."""

    def test_chunks_to_chroma_format_structure(self) -> None:
        """Converts chunks to (documents, metadatas, ids) tuple."""
        chunks = [
            Chunk(
                text="Test content",
                chunk_id="test_doc_0",
                provider="cme",
                document_name="test.pdf",
                section_heading="Section 1",
                page_start=1,
                page_end=2,
                chunk_index=0,
                word_count=2,
                is_definitions=False,
                document_version="1.0",
            )
        ]

        documents, metadatas, ids = chunks_to_chroma_format(chunks)

        assert len(documents) == 1
        assert len(metadatas) == 1
        assert len(ids) == 1
        assert documents[0] == "Test content"
        assert ids[0] == "test_doc_0"

    def test_chunks_to_chroma_format_metadata(self) -> None:
        """Metadata includes all required fields."""
        chunks = [
            Chunk(
                text="Test",
                chunk_id="cme_doc_0",
                provider="cme",
                document_name="doc.pdf",
                section_heading="Definitions",
                page_start=1,
                page_end=3,
                chunk_index=0,
                word_count=100,
                is_definitions=True,
                document_version="2.0",
            )
        ]

        _, metadatas, _ = chunks_to_chroma_format(chunks)
        meta = metadatas[0]

        assert meta["chunk_id"] == "cme_doc_0"
        assert meta["provider"] == "cme"
        assert meta["document_name"] == "doc.pdf"
        assert meta["section_heading"] == "Definitions"
        assert meta["page_start"] == 1
        assert meta["page_end"] == 3
        assert meta["chunk_index"] == 0
        assert meta["word_count"] == 100
        assert meta["is_definitions"] is True
        assert meta["document_version"] == "2.0"

    def test_chunks_to_chroma_format_multiple(self) -> None:
        """Handles multiple chunks correctly."""
        chunks = [
            Chunk(
                text=f"Content {i}",
                chunk_id=f"cme_doc_{i}",
                provider="cme",
                document_name="doc.pdf",
                section_heading="Section",
                page_start=i + 1,
                page_end=i + 1,
                chunk_index=i,
                word_count=10,
                is_definitions=False,
            )
            for i in range(5)
        ]

        documents, metadatas, ids = chunks_to_chroma_format(chunks)

        assert len(documents) == 5
        assert len(metadatas) == 5
        assert len(ids) == 5
        assert ids == ["cme_doc_0", "cme_doc_1", "cme_doc_2", "cme_doc_3", "cme_doc_4"]


class TestGetCollectionName:
    """Tests for collection name resolution."""

    def test_get_collection_name_known_provider(self) -> None:
        """Known provider returns configured collection name."""
        name = get_collection_name("cme")
        assert name == "cme_docs"

    def test_get_collection_name_unknown_provider(self) -> None:
        """Unknown provider returns default pattern."""
        name = get_collection_name("unknown_provider")
        assert name == "unknown_provider_docs"
