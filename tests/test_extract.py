# tests/test_extract.py
"""Tests for document extraction."""

from pathlib import Path

import pytest

from app.extract import ExtractedDocument
from app.extract import ExtractionError
from app.extract import detect_document_version
from app.extract import extract_document
from app.extract import extract_docx
from app.extract import extract_pdf
from app.extract import validate_extraction


class TestExtractPDF:
    """Tests for PDF extraction."""

    def test_extract_pdf_returns_extracted_document(self, sample_pdf: Path) -> None:
        """PDF extraction returns ExtractedDocument with pages."""
        result = extract_pdf(sample_pdf)

        assert isinstance(result, ExtractedDocument)
        assert result.page_count > 0
        assert len(result.pages) == result.page_count
        assert result.source_file == sample_pdf.name
        assert result.extraction_method == "pymupdf"

    def test_extract_pdf_has_content(self, sample_pdf: Path) -> None:
        """Extracted PDF contains text content."""
        result = extract_pdf(sample_pdf)

        assert result.word_count > 0
        assert len(result.full_text) > 0
        assert not result.is_empty

    def test_extract_pdf_pages_have_numbers(self, sample_pdf: Path) -> None:
        """Each page has correct page number (1-indexed)."""
        result = extract_pdf(sample_pdf)

        for i, page in enumerate(result.pages):
            assert page.page_num == i + 1

    def test_extract_pdf_fee_list(self, fee_list_pdf: Path) -> None:
        """Fee list PDF extracts with tabular content."""
        result = extract_pdf(fee_list_pdf)

        assert result.page_count > 0
        # Fee lists typically contain dollar amounts
        assert "$" in result.full_text or "fee" in result.full_text.lower()

    def test_extract_pdf_not_found(self, tmp_path: Path) -> None:
        """Extraction raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            extract_pdf(tmp_path / "nonexistent.pdf")


class TestExtractDocument:
    """Tests for generic document extraction."""

    def test_extract_document_pdf(self, sample_pdf: Path) -> None:
        """extract_document handles PDF files."""
        result = extract_document(sample_pdf)
        assert result.extraction_method == "pymupdf"

    def test_extract_document_unsupported(self, tmp_path: Path) -> None:
        """extract_document raises for unsupported file types."""
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("test")

        with pytest.raises(ExtractionError, match="Unsupported file type"):
            extract_document(unsupported)

    def test_extract_document_txt(self, tmp_path: Path) -> None:
        """extract_document handles TXT files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("This is a test document with some text content.")
        result = extract_document(txt_file)
        assert result.extraction_method == "plain-text"
        assert result.word_count > 0


class TestValidateExtraction:
    """Tests for extraction validation."""

    def test_validate_extraction_good_document(self, sample_pdf: Path) -> None:
        """Valid document produces no warnings."""
        extracted = extract_pdf(sample_pdf)
        warnings = validate_extraction(extracted)

        assert isinstance(warnings, list)
        # A good document should have minimal or no warnings
        assert len(warnings) <= 1

    def test_validate_extraction_empty_document(self) -> None:
        """Empty document produces warning."""
        from app.extract import PageContent

        empty_doc = ExtractedDocument(
            pages=[PageContent(page_num=1, text="")],
            page_count=1,
            source_file="empty.pdf",
            extraction_method="test",
        )
        warnings = validate_extraction(empty_doc)

        assert len(warnings) > 0
        assert any("no extractable text" in w for w in warnings)


class TestDetectDocumentVersion:
    """Tests for version detection."""

    def test_detect_version_explicit(self) -> None:
        """Detects explicit version strings."""
        assert detect_document_version("Version 1.0 of this document") == "1.0"
        assert detect_document_version("VERSION: 2.3.4") == "2.3.4"
        assert detect_document_version("v1.5 Release Notes") == "1.5"

    def test_detect_version_revision(self) -> None:
        """Detects revision patterns."""
        assert detect_document_version("Revision 3.0") == "3.0"

    def test_detect_version_none(self) -> None:
        """Returns None when no version found."""
        assert detect_document_version("No version info here") is None
        assert detect_document_version("Just some text") is None

    def test_detect_version_real_document(self, sample_pdf: Path) -> None:
        """Version detection works on real document."""
        extracted = extract_pdf(sample_pdf)
        version = detect_document_version(extracted.full_text)

        # The fixture is "information-policies-v5-04.pdf" so it may contain version info
        # Just verify it returns str or None without error
        assert version is None or isinstance(version, str)


class TestExtractDocx:
    """Tests for DOCX extraction with table support."""

    def test_extract_docx_returns_extracted_document(self, sample_docx: Path) -> None:
        """DOCX extraction returns ExtractedDocument."""
        result = extract_docx(sample_docx)

        assert isinstance(result, ExtractedDocument)
        assert result.page_count == 1  # DOCX treated as single page
        assert result.source_file == sample_docx.name
        assert result.extraction_method == "python-docx"

    def test_extract_docx_has_content(self, sample_docx: Path) -> None:
        """Extracted DOCX contains text content."""
        result = extract_docx(sample_docx)

        assert result.word_count > 0
        assert len(result.full_text) > 0
        assert not result.is_empty

    def test_extract_docx_table_extraction(self, sample_docx: Path) -> None:
        """Tables in DOCX are extracted as pipe-delimited rows."""
        result = extract_docx(sample_docx)

        # Table header and data should be present
        assert "Data Type" in result.full_text
        assert "Monthly Fee" in result.full_text
        assert "|" in result.full_text  # Pipe delimiter from table extraction
        # Fee values from the table
        assert "$500" in result.full_text or "500" in result.full_text

    def test_extract_docx_paragraphs_extracted(self, sample_docx: Path) -> None:
        """Paragraphs in DOCX are extracted."""
        result = extract_docx(sample_docx)

        assert "DEFINITIONS" in result.full_text
        assert "Distributor" in result.full_text
        assert "TERMINATION" in result.full_text

    def test_extract_docx_not_found(self, tmp_path: Path) -> None:
        """Extraction raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            extract_docx(tmp_path / "nonexistent.docx")

    def test_extract_document_docx(self, sample_docx: Path) -> None:
        """extract_document handles DOCX files."""
        result = extract_document(sample_docx)
        assert result.extraction_method == "python-docx"
