# tests/test_chunking.py
"""Tests for document chunking."""

from pathlib import Path

from app.chunking import Chunk
from app.chunking import _build_page_positions
from app.chunking import _find_page_range_by_position
from app.chunking import _is_important_short_section
from app.chunking import chunk_document
from app.chunking import detect_section_heading
from app.chunking import is_definitions_section
from app.chunking import is_fee_table_content
from app.chunking import split_by_sections
from app.chunking import window_chunk
from app.extract import ExtractedDocument
from app.extract import PageContent
from app.extract import extract_pdf


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

    def test_window_chunk_allow_short_preserves_tail(self) -> None:
        """With allow_short=True, short tail windows are preserved."""
        # Create text that will produce a chunk + short tail
        # 150 words = 1 full chunk of 100 + 50 word tail (below MIN_CHUNK_SIZE of 50)
        text = " ".join(f"word{i}" for i in range(150))

        # Without allow_short, tail may be dropped
        result_normal = window_chunk(text, size=100, overlap=20)

        # With allow_short, tail should be preserved
        result_short = window_chunk(text, size=100, overlap=20, allow_short=True)

        # allow_short should produce at least as many chunks
        # The key is that the tail window (words 80-149 = 70 words) is kept
        assert len(result_short) >= len(result_normal)

        # Verify last chunk exists and has content
        if result_short:
            last_chunk_text, _, _ = result_short[-1]
            assert len(last_chunk_text.split()) > 0

    def test_window_chunk_allow_short_single_small_chunk(self) -> None:
        """With allow_short=True, very short text is preserved."""
        # Just 10 words - below MIN_CHUNK_SIZE
        text = " ".join(f"word{i}" for i in range(10))

        # Without allow_short, would return empty
        _ = window_chunk(text, size=100, overlap=20, allow_short=False)

        # With allow_short, should preserve the content
        result_short = window_chunk(text, size=100, overlap=20, allow_short=True)

        assert len(result_short) == 1
        chunk_text, start, end = result_short[0]
        assert "word0" in chunk_text
        assert "word9" in chunk_text


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
        headings = [h for h, _, _, _ in result]
        assert any("SECTION 1" in h for h in headings)
        assert any("SECTION 2" in h for h in headings)

    def test_split_by_sections_indented_headers(self) -> None:
        """Indented section headers are detected."""
        text = """Preamble

    SECTION 1 Indented Section
    Content here."""

        result = split_by_sections(text)

        # Should detect indented section
        headings = [h for h, _, _, _ in result]
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


class TestIsFeeTableContent:
    """Tests for fee table detection."""

    def test_fee_table_with_multiple_dollar_amounts(self) -> None:
        """Detects fee tables with multiple dollar amounts."""
        fee_table = """
        Description         Monthly     Annually
        Real Time           $134.50     $1,614
        Delayed             $0          $0
        Non-Display         $609        $7,308
        """
        assert is_fee_table_content(fee_table)

    def test_fee_table_with_keywords(self) -> None:
        """Detects fee tables with fee keywords and dollar amounts."""
        text = "The monthly fee is $500 per device."
        assert is_fee_table_content(text)

    def test_non_fee_content(self) -> None:
        """Non-fee content returns False."""
        assert not is_fee_table_content("This is general license text without prices.")
        assert not is_fee_table_content("The subscriber shall comply with all terms.")

    def test_single_dollar_without_keywords(self) -> None:
        """Single dollar amount without fee keywords is not a fee table."""
        assert not is_fee_table_content("The value is $100.")


class TestIsImportantShortSection:
    """Tests for _is_important_short_section body-text scanning."""

    def test_heading_keyword_detected(self) -> None:
        """Heading with fee keyword returns True."""
        assert _is_important_short_section("Fee Schedule", "Some content")
        assert _is_important_short_section("EXHIBIT A", "Details")
        assert _is_important_short_section("SCHEDULE OF RATES", "Rate info")

    def test_body_text_keyword_detected(self) -> None:
        """Body text containing fee keywords returns True even without heading keywords."""
        # Heading has no keywords, but body mentions fees
        assert _is_important_short_section(
            "SECTION 5", "The monthly fee for data access shall be $500."
        )
        assert _is_important_short_section(
            "Article VII", "Payment is due within 30 days of invoice."
        )
        assert _is_important_short_section(
            "Part 3", "Termination of this agreement requires 90 days notice."
        )

    def test_definitions_section_detected(self) -> None:
        """Definitions sections are detected as important."""
        assert _is_important_short_section("ARTICLE I", "Definitions. 'Data' means...")

    def test_non_important_section(self) -> None:
        """Sections without important keywords return False."""
        assert not _is_important_short_section(
            "SECTION 1", "This agreement is entered into between the parties."
        )
        assert not _is_important_short_section(
            "Background", "The company was founded in 2020."
        )

    def test_body_scan_limited_to_500_chars(self) -> None:
        """Keywords beyond 500 chars in body are not detected."""
        # Fee keyword appears after 500 characters
        filler = "x" * 510
        assert not _is_important_short_section(
            "SECTION 1", f"{filler} The fee is $100."
        )


class TestSplitBySectionsOffsetAlignment:
    """Tests for section offset alignment with trimmed content."""

    def test_offsets_match_section_text(self) -> None:
        """Returned offsets slice the original text to get section_text."""
        text = """Preamble content here.

SECTION 1 First Section
   Content with leading whitespace.

SECTION 2 Second Section
More content here."""

        sections = split_by_sections(text)

        for heading, section_text, content_start, content_end in sections:
            # The slice from the original text must equal the section_text
            sliced = text[content_start:content_end]
            assert sliced == section_text, (
                f"Offset mismatch for '{heading}': "
                f"sliced={sliced!r}, section_text={section_text!r}"
            )

    def test_offsets_trim_whitespace(self) -> None:
        """Offsets exclude leading/trailing whitespace from sections."""
        text = """
SECTION 1 Test

   Some content here

"""
        sections = split_by_sections(text)

        for heading, section_text, content_start, content_end in sections:
            # section_text should have no leading/trailing whitespace
            assert section_text == section_text.strip()
            # Offsets should not include outer whitespace
            if content_start > 0:
                assert (
                    text[content_start - 1].isspace() or text[content_start - 1] == "\n"
                )
            if content_end < len(text):
                assert text[content_end].isspace() or text[content_end] == "\n"


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
        assert _find_page_range_by_position(
            page3_start + 10, page3_start + 50, positions, doc
        ) == (3, 3)


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
            assert chunk.source == "cme"
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
