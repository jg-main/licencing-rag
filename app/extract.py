# app/extract.py
"""Document text extraction with page tracking and quality validation."""

from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document

from app.logging import get_logger

log = get_logger(__name__)


class ExtractionError(Exception):
    """Raised when document extraction fails."""

    pass


@dataclass
class PageContent:
    """Content extracted from a single page."""

    page_num: int
    text: str


@dataclass
class ExtractedDocument:
    """Extracted document with pages and metadata."""

    pages: list[PageContent]
    page_count: int
    source_file: str
    extraction_method: str

    @property
    def full_text(self) -> str:
        """Get the full document text."""
        return "\n".join(page.text for page in self.pages)

    @property
    def word_count(self) -> int:
        """Get total word count."""
        return sum(len(page.text.split()) for page in self.pages)

    @property
    def is_empty(self) -> bool:
        """Check if document has no extractable content."""
        return self.word_count < 10


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract text and metadata from a PDF file.

    Args:
        path: Path to the PDF file.

    Returns:
        ExtractedDocument with pages and metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        ExtractionError: If PDF extraction fails or document is corrupted.
    """
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        doc = fitz.open(path)
    except Exception as e:
        log.error("pdf_open_failed", filename=path.name, error=str(e))
        raise ExtractionError(
            f"Cannot open PDF {path.name}: corrupted or invalid"
        ) from e

    try:
        pages = []
        for page in doc:
            pages.append(
                PageContent(
                    page_num=page.number + 1,  # 1-indexed
                    text=page.get_text(),
                )
            )
        doc.close()

        extracted = ExtractedDocument(
            pages=pages,
            page_count=len(pages),
            source_file=path.name,
            extraction_method="pymupdf",
        )

        # Validate extraction quality
        if extracted.is_empty:
            log.warning(
                "extraction_empty",
                filename=path.name,
                pages=len(pages),
                words=extracted.word_count,
            )

        log.debug(
            "pdf_extracted",
            filename=path.name,
            pages=extracted.page_count,
            words=extracted.word_count,
        )
        return extracted

    except Exception as e:
        doc.close()
        log.error("pdf_extraction_failed", filename=path.name, error=str(e))
        raise ExtractionError(f"Failed to extract PDF {path.name}: {e}") from e


def extract_docx(path: Path) -> ExtractedDocument:
    """Extract text from a DOCX file.

    Note: DOCX files don't have page numbers in the same way as PDFs.
    Each paragraph is treated as belonging to page 1.

    Args:
        path: Path to the DOCX file.

    Returns:
        ExtractedDocument with content and metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        ExtractionError: If DOCX extraction fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"DOCX file not found: {path}")

    try:
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        # DOCX doesn't have page boundaries, treat as single page
        pages = [PageContent(page_num=1, text=full_text)]

        extracted = ExtractedDocument(
            pages=pages,
            page_count=1,
            source_file=path.name,
            extraction_method="python-docx",
        )

        if extracted.is_empty:
            log.warning(
                "extraction_empty", filename=path.name, words=extracted.word_count
            )

        log.debug("docx_extracted", filename=path.name, words=extracted.word_count)
        return extracted
    except Exception as e:
        log.error("docx_extraction_failed", filename=path.name, error=str(e))
        raise ExtractionError(f"Failed to extract DOCX {path.name}: {e}") from e


def extract_document(path: Path) -> ExtractedDocument:
    """Extract text from a document based on its extension.

    Args:
        path: Path to the document file.

    Returns:
        ExtractedDocument with content and metadata.

    Raises:
        ExtractionError: If extraction fails or file type is not supported.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    elif suffix == ".docx":
        return extract_docx(path)
    else:
        log.error("unsupported_file_type", filename=path.name, suffix=suffix)
        raise ExtractionError(f"Unsupported file type: {suffix}")


def validate_extraction(extracted: ExtractedDocument) -> list[str]:
    """Validate extraction quality and return warnings.

    Args:
        extracted: The extracted document to validate.

    Returns:
        List of warning messages. Empty list if no issues.
    """
    warnings = []

    if extracted.is_empty:
        warnings.append(f"Document '{extracted.source_file}' has no extractable text")

    if extracted.page_count == 0:
        warnings.append(f"Document '{extracted.source_file}' has no pages")

    # Check for potential OCR issues (mostly non-text characters)
    text = extracted.full_text
    if text:
        alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text), 1)
        if alpha_ratio < 0.3:
            warnings.append(
                f"Document '{extracted.source_file}' may need OCR "
                f"(only {alpha_ratio:.0%} alphabetic)"
            )

    for warning in warnings:
        log.warning("extraction_validation", message=warning)

    return warnings
