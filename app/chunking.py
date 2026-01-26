# app/chunking.py
"""Document chunking with section detection and metadata tracking."""

import re
from dataclasses import dataclass

from app.config import CHUNK_OVERLAP
from app.config import CHUNK_SIZE
from app.config import MIN_CHUNK_SIZE
from app.extract import ExtractedDocument

# Section detection patterns (priority order)
SECTION_PATTERNS = [
    re.compile(r"^SECTION\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Article\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^ARTICLE\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\d+\.\d+(\.\d+)*\s+", re.MULTILINE),
    re.compile(r"^EXHIBIT\s+[A-Z0-9]", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^SCHEDULE\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^APPENDIX\s+[A-Z0-9]", re.MULTILINE | re.IGNORECASE),
]

# Combined pattern for initial splitting
SECTION_REGEX = re.compile(
    r"(?m)^(SECTION\s+\d+|Article\s+[IVXLCDM]+|ARTICLE\s+\d+|"
    r"\d+\.\d+(\.\d+)*\s+|EXHIBIT\s+[A-Z0-9]|SCHEDULE\s+\d+|APPENDIX\s+[A-Z0-9]).*$",
    re.IGNORECASE,
)


@dataclass
class Chunk:
    """A document chunk with metadata."""

    text: str
    chunk_id: str
    provider: str
    document_name: str
    section_heading: str
    page_start: int
    page_end: int
    chunk_index: int
    word_count: int
    is_definitions: bool = False


def detect_section_heading(text: str) -> str:
    """Detect section heading from text.

    Args:
        text: Text to search for section heading.

    Returns:
        Detected section heading or "N/A".
    """
    for pattern in SECTION_PATTERNS:
        match = pattern.search(text[:500])  # Check first 500 chars
        if match:
            # Get the full line containing the match
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = min(match.end() + 100, len(text))
            heading = text[line_start:line_end].strip()
            # Truncate if too long
            return heading[:100] if len(heading) > 100 else heading
    return "N/A"


def is_definitions_section(text: str) -> bool:
    """Check if text appears to be a definitions section.

    Args:
        text: Text to check.

    Returns:
        True if this appears to be a definitions section.
    """
    lower_text = text[:500].lower()
    return "definition" in lower_text or "defined term" in lower_text


def split_by_sections(text: str) -> list[tuple[str, str]]:
    """Split text by section boundaries.

    Args:
        text: Full document text.

    Returns:
        List of (section_heading, section_text) tuples.
    """
    matches = list(SECTION_REGEX.finditer(text))
    if not matches:
        return [("N/A", text)]

    sections = []

    # Add any text before the first section
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("Preamble", preamble))

    # Process each section
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        heading = match.group(0).strip()
        sections.append((heading, section_text))

    return sections


def window_chunk(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping word windows.

    Args:
        text: Text to chunk.
        size: Target chunk size in words.
        overlap: Overlap between chunks in words.

    Returns:
        List of text chunks.
    """
    words = text.split()
    if len(words) <= size:
        return [text] if len(words) >= MIN_CHUNK_SIZE else []

    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + size]
        if len(chunk_words) >= MIN_CHUNK_SIZE:
            chunks.append(" ".join(chunk_words))
        i += size - overlap

    return chunks


def find_page_range(
    chunk_text: str,
    document: ExtractedDocument,
) -> tuple[int, int]:
    """Find the page range for a chunk.

    Args:
        chunk_text: The chunk text to locate.
        document: The source document with page information.

    Returns:
        Tuple of (page_start, page_end).
    """
    # Simple heuristic: find which pages contain parts of the chunk
    chunk_start = chunk_text[:100]  # First 100 chars for matching
    page_start = 1
    page_end = 1

    for page in document.pages:
        if chunk_start in page.text:
            page_start = page.page_num
            break

    # Check if chunk spans multiple pages
    chunk_end = chunk_text[-100:] if len(chunk_text) > 100 else chunk_text
    for page in document.pages:
        if chunk_end in page.text:
            page_end = page.page_num

    return page_start, max(page_start, page_end)


def chunk_document(
    document: ExtractedDocument,
    provider: str,
) -> list[Chunk]:
    """Chunk a document with full metadata.

    Args:
        document: Extracted document to chunk.
        provider: Provider identifier (e.g., "cme").

    Returns:
        List of Chunk objects with metadata.
    """
    full_text = document.full_text
    sections = split_by_sections(full_text)

    chunks: list[Chunk] = []
    chunk_index = 0

    for section_heading, section_text in sections:
        text_chunks = window_chunk(section_text)

        for text in text_chunks:
            page_start, page_end = find_page_range(text, document)
            word_count = len(text.split())

            chunk = Chunk(
                text=text,
                chunk_id=f"{provider}_{document.source_file}_{chunk_index}",
                provider=provider,
                document_name=document.source_file,
                section_heading=section_heading,
                page_start=page_start,
                page_end=page_end,
                chunk_index=chunk_index,
                word_count=word_count,
                is_definitions=is_definitions_section(text),
            )
            chunks.append(chunk)
            chunk_index += 1

    return chunks
