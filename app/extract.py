# app/extract.py
"""Document text extraction with page tracking."""

from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document


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


def extract_pdf(path: Path) -> ExtractedDocument:
    """Extract text and metadata from a PDF file.

    Args:
        path: Path to the PDF file.

    Returns:
        ExtractedDocument with pages and metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If PDF extraction fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    try:
        doc = fitz.open(path)
        pages = []
        for page in doc:
            pages.append(
                PageContent(
                    page_num=page.number + 1,  # 1-indexed
                    text=page.get_text(),
                )
            )
        doc.close()

        return ExtractedDocument(
            pages=pages,
            page_count=len(pages),
            source_file=path.name,
            extraction_method="pymupdf",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to extract PDF {path}: {e}") from e


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
        RuntimeError: If DOCX extraction fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"DOCX file not found: {path}")

    try:
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n".join(paragraphs)

        # DOCX doesn't have page boundaries, treat as single page
        pages = [PageContent(page_num=1, text=full_text)]

        return ExtractedDocument(
            pages=pages,
            page_count=1,
            source_file=path.name,
            extraction_method="python-docx",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to extract DOCX {path}: {e}") from e


def extract_document(path: Path) -> ExtractedDocument:
    """Extract text from a document based on its extension.

    Args:
        path: Path to the document file.

    Returns:
        ExtractedDocument with content and metadata.

    Raises:
        ValueError: If the file type is not supported.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    elif suffix == ".docx":
        return extract_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
