# tests/test_ingest.py
"""Tests for document ingestion."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.chunking import Chunk
from app.ingest import chunks_to_chroma_format, get_collection_name, prune_deleted_documents


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
                document_path="test.pdf",
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
                document_path="Fees/doc.pdf",
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
        assert meta["document_path"] == "Fees/doc.pdf"
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
                document_path="doc.pdf",
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

    def test_chunks_to_chroma_format_filters_none_values(self) -> None:
        """Filters out None values from metadata (ChromaDB rejects None)."""
        chunks = [
            Chunk(
                text="Test content",
                chunk_id="test_doc_0",
                provider="cme",
                document_name="test.pdf",
                document_path="test.pdf",
                section_heading="Section 1",
                page_start=1,
                page_end=2,
                chunk_index=0,
                word_count=2,
                is_definitions=False,
                document_version=None,  # This should be filtered out
            )
        ]

        _, metadatas, _ = chunks_to_chroma_format(chunks)
        meta = metadatas[0]

        # document_version should NOT be in metadata when None
        assert "document_version" not in meta
        # Other fields should still be present
        assert meta["chunk_id"] == "test_doc_0"
        assert meta["document_path"] == "test.pdf"


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


class TestPruneDeletedDocuments:
    """Tests for pruning chunks of deleted documents."""

    def test_prune_deleted_documents_removes_stale_chunks(self) -> None:
        """Chunks from deleted documents are removed from collection."""
        # Create mock collection with chunks from 3 documents
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["doc1_0", "doc1_1", "doc2_0", "doc3_0", "doc3_1"],
            "metadatas": [
                {"document_path": "file1.pdf", "chunk_id": "doc1_0"},
                {"document_path": "file1.pdf", "chunk_id": "doc1_1"},
                {"document_path": "file2.pdf", "chunk_id": "doc2_0"},
                {"document_path": "subdir/file3.pdf", "chunk_id": "doc3_0"},
                {"document_path": "subdir/file3.pdf", "chunk_id": "doc3_1"},
            ],
        }

        # Current documents: only file1.pdf and subdir/file3.pdf exist
        # file2.pdf has been deleted
        current_doc_paths = {"file1.pdf", "subdir/file3.pdf"}

        deleted_count = prune_deleted_documents("cme", mock_collection, current_doc_paths)

        # Should delete 1 chunk from file2.pdf
        assert deleted_count == 1
        mock_collection.delete.assert_called_once_with(ids=["doc2_0"])

    def test_prune_deleted_documents_no_stale_chunks(self) -> None:
        """No deletions when all indexed documents still exist."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["doc1_0", "doc2_0"],
            "metadatas": [
                {"document_path": "file1.pdf", "chunk_id": "doc1_0"},
                {"document_path": "file2.pdf", "chunk_id": "doc2_0"},
            ],
        }

        current_doc_paths = {"file1.pdf", "file2.pdf"}

        deleted_count = prune_deleted_documents("cme", mock_collection, current_doc_paths)

        assert deleted_count == 0
        mock_collection.delete.assert_not_called()

    def test_prune_deleted_documents_empty_collection(self) -> None:
        """Handles empty collection gracefully."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"ids": [], "metadatas": []}

        current_doc_paths = {"file1.pdf"}

        deleted_count = prune_deleted_documents("cme", mock_collection, current_doc_paths)

        assert deleted_count == 0
        mock_collection.delete.assert_not_called()

    def test_prune_deleted_documents_backward_compat_document_name(self) -> None:
        """Falls back to document_name if document_path is missing."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["doc1_0", "doc2_0"],
            "metadatas": [
                {"document_name": "file1.pdf", "chunk_id": "doc1_0"},  # Old metadata
                {"document_path": "file2.pdf", "chunk_id": "doc2_0"},  # New metadata
            ],
        }

        # Only file2.pdf exists (file1.pdf deleted)
        current_doc_paths = {"file2.pdf"}

        deleted_count = prune_deleted_documents("cme", mock_collection, current_doc_paths)

        # Should delete chunk from file1.pdf
        assert deleted_count == 1
        mock_collection.delete.assert_called_once_with(ids=["doc1_0"])


class TestStaleChunkCleanup:
    """Tests for stale chunk cleanup on extraction failure."""

    def test_extraction_failure_removes_stale_chunks(self) -> None:
        """When extraction fails, existing chunks are deleted before the failure."""
        from pathlib import Path
        from unittest.mock import MagicMock, patch
        from app.ingest import ingest_provider
        from app.extract import ExtractionError

        with patch("app.ingest.chromadb.PersistentClient") as mock_client, \
             patch("app.ingest.extract_document") as mock_extract, \
             patch("app.ingest.BM25Index") as mock_bm25_class:
            
            # Setup mock collection
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "ids": ["old_chunk_1", "old_chunk_2"],
                "metadatas": [
                    {"document_path": "test.pdf", "chunk_id": "old_chunk_1"},
                    {"document_path": "test.pdf", "chunk_id": "old_chunk_2"},
                ],
            }
            mock_client.return_value.get_or_create_collection.return_value = mock_collection
            
            # Mock extraction to fail
            mock_extract.side_effect = ExtractionError("Corrupted PDF")
            
            # Mock BM25 index
            mock_bm25_instance = MagicMock()
            mock_bm25_class.return_value = mock_bm25_instance
            
            # Create temp directory with a test file
            with patch("app.ingest.get_provider_raw_dir") as mock_raw_dir:
                temp_dir = Path("/tmp/test_provider")
                mock_raw_dir.return_value = temp_dir
                
                # Mock the file existence check
                with patch.object(Path, "exists", return_value=True), \
                     patch.object(Path, "rglob") as mock_rglob:
                    
                    # Mock finding one PDF file
                    test_file = temp_dir / "test.pdf"
                    mock_rglob.return_value = [test_file]
                    
                    # Mock file check
                    with patch.object(Path, "is_file", return_value=True), \
                         patch.object(Path, "suffix", new_callable=lambda: property(lambda self: ".pdf")), \
                         patch.object(Path, "relative_to", return_value=Path("test.pdf")):
                        
                        # Run ingestion
                        result = ingest_provider("cme", force=False)
            
            # Verify old chunks were deleted BEFORE extraction failed
            mock_collection.delete.assert_called_once_with(
                ids=["old_chunk_1", "old_chunk_2"]
            )
            
            # Verify extraction was attempted
            mock_extract.assert_called_once()
            
            # Verify no new chunks were added (extraction failed)
            mock_collection.add.assert_not_called()
            
            # Verify error was reported
            assert len(result["errors"]) == 1
            assert "Extraction failed" in result["errors"][0]


