"""Test subdirectory support for ingestion pipeline."""

import shutil
from pathlib import Path

import pytest

from app.chunking import chunk_document
from app.chunking import save_chunks_artifacts
from app.extract import save_extraction_artifacts


class TestSubdirectoryDiscovery:
    """Test recursive file discovery across subdirectories."""

    def test_rglob_finds_files_in_subdirectories(self, tmp_path):
        """Verify rglob recursively discovers files in subdirectories."""
        # Create subdirectory structure
        fees_dir = tmp_path / "raw" / "test_provider" / "Fees"
        agreements_dir = tmp_path / "raw" / "test_provider" / "Agreements"
        fees_dir.mkdir(parents=True)
        agreements_dir.mkdir(parents=True)

        # Create test files
        (fees_dir / "fee1.pdf").write_text("fee content")
        (fees_dir / "fee2.pdf").write_text("fee content")
        (agreements_dir / "agreement1.pdf").write_text("agreement content")
        (agreements_dir / "agreement2.docx").write_text("agreement content")

        # Test discovery
        raw_dir = tmp_path / "raw" / "test_provider"
        supported_extensions = {".pdf", ".docx"}
        doc_files = sorted(
            [
                f
                for f in raw_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ],
            key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
        )

        assert len(doc_files) == 4
        # Verify deterministic ordering by relative path
        relative_paths = [f.relative_to(raw_dir).as_posix() for f in doc_files]
        assert relative_paths == [
            "Agreements/agreement1.pdf",
            "Agreements/agreement2.docx",
            "Fees/fee1.pdf",
            "Fees/fee2.pdf",
        ]

    def test_flat_structure_still_works(self, tmp_path):
        """Verify backward compatibility with flat directory structure."""
        raw_dir = tmp_path / "raw" / "test_provider"
        raw_dir.mkdir(parents=True)

        # Create test files in flat structure
        (raw_dir / "doc1.pdf").write_text("content1")
        (raw_dir / "doc2.pdf").write_text("content2")

        # Test discovery
        supported_extensions = {".pdf", ".docx"}
        doc_files = sorted(
            [
                f
                for f in raw_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ],
            key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
        )

        assert len(doc_files) == 2
        relative_paths = [f.relative_to(raw_dir).as_posix() for f in doc_files]
        assert relative_paths == ["doc1.pdf", "doc2.pdf"]

    def test_nested_subdirectories(self, tmp_path):
        """Verify deeply nested subdirectories are discovered."""
        deep_dir = tmp_path / "raw" / "test_provider" / "Level1" / "Level2" / "Level3"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.pdf").write_text("deep content")

        raw_dir = tmp_path / "raw" / "test_provider"
        supported_extensions = {".pdf", ".docx"}
        doc_files = sorted(
            [
                f
                for f in raw_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ],
            key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
        )

        assert len(doc_files) == 1
        relative_path = doc_files[0].relative_to(raw_dir).as_posix()
        assert relative_path == "Level1/Level2/Level3/deep.pdf"


class TestArtifactNaming:
    """Test path-encoded artifact naming to prevent collisions."""

    def test_extraction_artifact_path_encoding(self, tmp_path):
        """Verify extraction artifacts use path encoding for subdirectories."""
        # Create a mock extracted document using dataclass
        from app.extract import ExtractedDocument
        from app.extract import PageContent

        extracted = ExtractedDocument(
            source_file="test.pdf",
            pages=[PageContent(page_num=1, text="Test content")],
            page_count=1,
            extraction_method="test",
        )

        output_dir = tmp_path / "text"
        relative_path = Path("Fees/schedule.pdf")

        text_path, meta_path = save_extraction_artifacts(
            extracted, output_dir, "test_provider", relative_path
        )

        # Verify path encoding: Fees/schedule.pdf -> Fees__schedule.pdf
        assert text_path.name == "Fees__schedule.pdf.txt"
        assert meta_path.name == "Fees__schedule.pdf.meta.json"
        assert text_path.exists()
        assert meta_path.exists()

    def test_extraction_artifact_backward_compatibility(self, tmp_path):
        """Verify extraction artifacts work without relative_path (flat structure)."""
        from app.extract import ExtractedDocument
        from app.extract import PageContent

        extracted = ExtractedDocument(
            source_file="document.pdf",
            pages=[PageContent(page_num=1, text="Test content")],
            page_count=1,
            extraction_method="test",
        )

        output_dir = tmp_path / "text"

        # Call without relative_path (legacy behavior)
        text_path, meta_path = save_extraction_artifacts(
            extracted, output_dir, "test_provider"
        )

        assert text_path.name == "document.pdf.txt"
        assert meta_path.name == "document.pdf.meta.json"

    def test_chunk_artifact_path_encoding(self, tmp_path):
        """Verify chunk artifacts use path encoding for subdirectories."""
        from app.chunking import Chunk

        chunks = [
            Chunk(
                text="Test chunk",
                chunk_id="test_0",
                source="test_provider",
                document_name="test.pdf",
                document_path="Agreements/test.pdf",
                section_heading="Section 1",
                page_start=1,
                page_end=1,
                chunk_index=0,
                word_count=2,
                is_definitions=False,
                document_version="v1",
            )
        ]

        output_dir = tmp_path / "chunks"
        relative_path = Path("Agreements/license.pdf")

        chunks_path, meta_path = save_chunks_artifacts(
            chunks, relative_path, output_dir
        )

        # Verify path encoding: Agreements/license.pdf -> Agreements__license
        assert chunks_path.name == "Agreements__license.chunks.jsonl"
        assert meta_path.name == "Agreements__license.chunks.meta.json"
        assert chunks_path.exists()
        assert meta_path.exists()

    def test_chunk_artifact_backward_compatibility(self, tmp_path):
        """Verify chunk artifacts work with string document_name (flat structure)."""
        from app.chunking import Chunk

        chunks = [
            Chunk(
                text="Test chunk",
                chunk_id="test_0",
                source="test_provider",
                document_name="test.pdf",
                document_path="test.pdf",
                section_heading="Section 1",
                page_start=1,
                page_end=1,
                chunk_index=0,
                word_count=2,
                is_definitions=False,
                document_version="v1",
            )
        ]

        output_dir = tmp_path / "chunks"

        # Call with string (legacy behavior)
        chunks_path, meta_path = save_chunks_artifacts(
            chunks, "document.pdf", output_dir
        )

        assert chunks_path.name == "document.chunks.jsonl"
        assert meta_path.name == "document.chunks.meta.json"


class TestCollisionPrevention:
    """Test that subdirectories prevent filename collisions."""

    def test_same_filename_different_subdirs_no_collision(self, tmp_path):
        """Verify same filename in different subdirectories creates distinct artifacts."""
        from app.extract import ExtractedDocument
        from app.extract import PageContent

        extracted = ExtractedDocument(
            source_file="agreement.pdf",
            pages=[PageContent(page_num=1, text="Test content")],
            page_count=1,
            extraction_method="test",
        )

        output_dir = tmp_path / "text"

        # Save from Fees subdirectory
        text_path1, _ = save_extraction_artifacts(
            extracted, output_dir, "test", Path("Fees/agreement.pdf")
        )

        # Save from Agreements subdirectory (same filename)
        text_path2, _ = save_extraction_artifacts(
            extracted, output_dir, "test", Path("Agreements/agreement.pdf")
        )

        # Verify distinct artifacts
        assert text_path1.name == "Fees__agreement.pdf.txt"
        assert text_path2.name == "Agreements__agreement.pdf.txt"
        assert text_path1 != text_path2
        assert text_path1.exists() and text_path2.exists()


class TestChunkIDUniqueness:
    """Test chunk IDs include encoded paths for uniqueness."""

    def test_chunk_ids_include_relative_path(self):
        """Verify chunk IDs use encoded relative path to ensure uniqueness."""
        from app.extract import ExtractedDocument
        from app.extract import PageContent

        # Create longer text that will actually chunk
        text = "Section 1: Fees and Charges\n\n" + " ".join(
            ["This is test content."] * 50
        )

        extracted = ExtractedDocument(
            source_file="test.pdf",
            pages=[PageContent(page_num=1, text=text)],
            page_count=1,
            extraction_method="test",
        )

        relative_path = Path("Fees/schedule.pdf")

        chunks = chunk_document(
            extracted,
            source="test_provider",
            document_version="v1",
            relative_path=relative_path,
        )

        # Verify chunk IDs use encoded path
        assert len(chunks) > 0
        for chunk in chunks:
            assert "Fees__schedule.pdf" in chunk.chunk_id
            assert chunk.chunk_id.startswith("test_provider_Fees__schedule.pdf_")

    def test_chunk_ids_backward_compatible(self):
        """Verify chunk IDs work without relative_path (flat structure)."""
        from app.extract import ExtractedDocument
        from app.extract import PageContent

        # Create longer text that will actually chunk
        text = "Section 1: Overview\n\n" + " ".join(
            ["This is test document content."] * 50
        )

        extracted = ExtractedDocument(
            source_file="test.pdf",
            pages=[PageContent(page_num=1, text=text)],
            page_count=1,
            extraction_method="test",
        )

        # Call without relative_path
        chunks = chunk_document(
            extracted,
            source="test_provider",
            document_version="v1",
        )

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.chunk_id.startswith("test_provider_test.pdf_")


class TestEndToEndSubdirectories:
    """End-to-end tests with real fixture files in subdirectories."""

    def test_deterministic_ordering_across_subdirs(self, tmp_path):
        """Verify ingestion order is deterministic across subdirectories."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "subdir_test"

        if not fixtures_dir.exists():
            pytest.skip("Subdirectory test fixtures not available")

        raw_dir = tmp_path / "raw" / "test_provider"
        shutil.copytree(fixtures_dir, raw_dir)

        # Find files twice
        supported_extensions = {".pdf", ".docx"}

        files1 = sorted(
            [
                f
                for f in raw_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ],
            key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
        )

        files2 = sorted(
            [
                f
                for f in raw_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in supported_extensions
            ],
            key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
        )

        # Verify identical ordering
        assert files1 == files2

        # Verify alphabetical by relative path
        rel_paths = [f.relative_to(raw_dir).as_posix() for f in files1]
        assert rel_paths == sorted(rel_paths)
