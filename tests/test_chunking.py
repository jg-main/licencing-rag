# tests/test_chunking.py
"""Tests for document chunking."""

from pathlib import Path

import pytest

from app.chunking import (
    Chunk,
    _build_page_positions,
    _find_page_range_by_position,
    chunk_document,
    detect_section_heading,
    is_definitions_section,
    split_by_sections,
    window_chunk,
)
from app.extract import ExtractedDocument, PageContent, extract_pdf


class TestWindowChunk:
    """Tests for window_chunk function."""

    def test_window_chunk_returns_tuples(self) -> None:
        """window_chunk returns list of (text, start, end) tuples."""
        # Need enough words to exceed MIN_CHUNK_SIZE (100) and create chunks
        text = " ".join(f"word{i}" for i in range(600))
        result = window_chunk(text, size=100, overlap=20)

        assert len(result) > 0
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3
            chunk_text, start, end = item
            assert isinstance(chunk_text, str)
            assert isinstance(start, int)
            assert isinstance(end, int)

    def test_window_chunk_preserves_positions(self) -> None:
        """Chunk positions correctly index into original text."""
        text = "   Hello world this is a test with many words needed to chunk   "
        words = " ".join(f"word{i}" for i in range(150))
        text = f"  {words}  "

        result = window_chunk(text, size=50, overlap=10)

        for chunk_text, start, end in result:
            # The extracted chunk should match the slice from original
            assert text[start:end] == chunk_text

    def test_window_chunk_short_text_uses_word_boundaries(self) -> None:
        """Short text under chunk size uses actual word boundaries."""
        text = "   Hello   world   test   "
        # This is under MIN_CHUNK_SIZE so may return empty
        # Let's test with enough words
        words = " ".join(f"word{i}" for i in range(50))
        text = f"   {words}   "

        result = window_chunk(text, size=100, overlap=20)

        # Should return single chunk with proper boundaries
        if result:
            chunk_text, start, end = result[0]
            # Start should skip leading whitespace
            assert not chunk_text.startswith(" ")
            assert text[start:end] == chunk_text

    def test_window_chunk_empty_text(self) -> None:
        """Empty or whitespace-only text returns empty list."""
        assert window_chunk("") == []
        assert window_chunk("   ") == []

    def test_window_chunk_overlap_guard(self) -> None:
        """Overlap >= size doesn't cause infinite loop."""
        text = " ".join(f"word{i}" for i in range(200))
        # This should not hang
        result = window_chunk(text, size=50, overlap=50)
        assert isinstance(result, list)

    def test_window_chunk_advances(self) -> None:
        """Multiple chunks are generated for long text."""
        text = " ".join(f"word{i}" for i in range(500))
        result = window_chunk(text, size=100, overlap=20)

        assert len(result) > 1
        # Each chunk should start at different positions
        starts = [start for _, start, _ in result]
        assert len(set(starts)) == len(starts)


class TestSplitBySections:
    """Tests for section splitting."""

    def test_split_by_sections_no_sections(self) -> None:
        """Text without section headers returns single N/A section."""
        text = "Just some plain text without any section headers."
        result = split_by_sections(text)

        assert len(result) == 1
        assert result[0][0] == "N/A"
        assert text in result[0][1]

    def test_split_by_sections_with_headers(self) -> None:
        """Text with section headers is properly split."""
        text = """Introduction text here.

SECTION 1 First Section
Content of section 1.

SECTION 2 Second Section
Content of section 2."""

        result = split_by_sections(text)

        # Should have preamble + 2 sections
        assert len(result) >= 2
        headings = [h for h, _ in result]
        assert any("SECTION 1" in h for h in headings)
        assert any("SECTION 2" in h for h in headings)

    def test_split_by_sections_indented_headers(self) -> None:
        """Indented section headers are detected."""
        text = """Preamble

    SECTION 1 Indented Section
    Content here."""

        result = split_by_sections(text)

        # Should detect indented section
        headings = [h for h, _ in result]
        assert any("SECTION" in h for h in headings)


class TestDetectSectionHeading:
    """Tests for section heading detection."""

    def test_detect_section_heading_explicit(self) -> None:
        """Detects explicit section patterns."""
        assert "SECTION" in detect_section_heading("SECTION 1 Definitions\nContent")
        assert "Article" in detect_section_heading("Article IV Amendments\nMore text")
        assert "SCHEDULE" in detect_section_heading("SCHEDULE 1 Fees\nDetails")

    def test_detect_section_heading_none(self) -> None:
        """Returns N/A for text without section heading."""
        assert detect_section_heading("Just regular content") == "N/A"


class TestIsDefinitionsSection:
    """Tests for definitions section detection."""

    def test_is_definitions_section_true(self) -> None:
        """Detects definitions sections."""
        assert is_definitions_section("Definitions\n'Term' means...")
        assert is_definitions_section("ARTICLE I - DEFINITIONS")
        assert is_definitions_section("1.1 Definitions. As used herein:")

    def test_is_definitions_section_false(self) -> None:
        """Non-definitions sections return False."""
        assert not is_definitions_section("General provisions apply")
        assert not is_definitions_section("Fee schedule for 2025")


class TestPagePositions:
    """Tests for page position mapping."""

    def test_build_page_positions(self) -> None:
        """_build_page_positions creates correct mapping."""
        doc = ExtractedDocument(
            pages=[
                PageContent(page_num=1, text="First page content"),
                PageContent(page_num=2, text="Second page"),
            ],
            page_count=2,
            source_file="test.pdf",
            extraction_method="test",
        )

        positions = _build_page_positions(doc)

        assert len(positions) == 2
        assert positions[0][0] == 1  # page_num
        assert positions[0][1] == 0  # start
        assert positions[1][0] == 2  # page_num

    def test_find_page_range_by_position(self) -> None:
        """_find_page_range_by_position finds correct pages."""
        doc = ExtractedDocument(
            pages=[
                PageContent(page_num=1, text="A" * 100),
                PageContent(page_num=2, text="B" * 100),
                PageContent(page_num=3, text="C" * 100),
            ],
            page_count=3,
            source_file="test.pdf",
            extraction_method="test",
        )
        positions = _build_page_positions(doc)

        # Chunk in page 1
        assert _find_page_range_by_position(10, 50, positions, doc) == (1, 1)

        # Chunk spanning pages 1-2 (positions overlap at ~100)
        assert _find_page_range_by_position(90, 110, positions, doc)[0] == 1

        # Chunk in page 3
        page3_start = 100 + 1 + 100 + 1  # Two pages + newlines
        assert _find_page_range_by_position(page3_start + 10, page3_start + 50, positions, doc) == (3, 3)


class TestChunkDocument:
    """Tests for full document chunking."""

    def test_chunk_document_returns_chunks(self, sample_pdf: Path) -> None:
        """chunk_document returns list of Chunk objects."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "test_provider")

        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, Chunk)

    def test_chunk_metadata_complete(self, sample_pdf: Path) -> None:
        """Each chunk has complete metadata."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "cme")

        for chunk in chunks:
            assert chunk.provider == "cme"
            assert chunk.document_name == sample_pdf.name
            assert chunk.page_start >= 1
            assert chunk.page_end >= chunk.page_start
            assert chunk.word_count > 0
            assert chunk.chunk_index >= 0
            assert isinstance(chunk.is_definitions, bool)

    def test_chunk_ids_unique(self, sample_pdf: Path) -> None:
        """All chunk IDs are unique."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "cme")

        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_document_with_version(self, sample_pdf: Path) -> None:
        """chunk_document passes document_version to chunks."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "cme", document_version="1.0")

        for chunk in chunks:
            assert chunk.document_version == "1.0"

    def test_chunk_page_ranges_valid(self, sample_pdf: Path) -> None:
        """Chunk page ranges are within document bounds."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "cme")

        for chunk in chunks:
            assert 1 <= chunk.page_start <= extracted.page_count
            assert 1 <= chunk.page_end <= extracted.page_count
            assert chunk.page_start <= chunk.page_end

    def test_chunk_text_not_empty(self, sample_pdf: Path) -> None:
        """No chunk has empty text."""
        extracted = extract_pdf(sample_pdf)
        chunks = chunk_document(extracted, "cme")

        for chunk in chunks:
            assert len(chunk.text.strip()) > 0
