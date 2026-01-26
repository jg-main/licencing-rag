# app/chunking.py
"""Document chunking with section detection and metadata tracking."""

import re
from dataclasses import dataclass
from pathlib import Path

from app.config import CHUNK_OVERLAP
from app.config import CHUNK_SIZE
from app.config import MIN_CHUNK_SIZE
from app.extract import ExtractedDocument
from app.logging import get_logger

log = get_logger(__name__)

# Section detection patterns (priority order)
# Allow optional leading whitespace (up to 8 spaces or 2 tabs) for indented headers
_WS = r"^[ \t]{0,8}"
SECTION_PATTERNS = [
    re.compile(_WS + r"SECTION\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(_WS + r"Article\s+[IVXLCDM]+", re.MULTILINE | re.IGNORECASE),
    re.compile(_WS + r"ARTICLE\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(_WS + r"\d+\.\d+(\.\d+)*\s+", re.MULTILINE),
    re.compile(_WS + r"EXHIBIT\s+[A-Z0-9]", re.MULTILINE | re.IGNORECASE),
    re.compile(_WS + r"SCHEDULE\s+\d+", re.MULTILINE | re.IGNORECASE),
    re.compile(_WS + r"APPENDIX\s+[A-Z0-9]", re.MULTILINE | re.IGNORECASE),
]

# Combined pattern for initial splitting (allows optional leading whitespace)
SECTION_REGEX = re.compile(
    r"(?m)^[ \t]{0,8}(SECTION\s+\d+|Article\s+[IVXLCDM]+|ARTICLE\s+\d+|"
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
    document_version: str | None = None


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
) -> list[tuple[str, int, int]]:
    """Split text into overlapping word windows, preserving original spans.

    Args:
        text: Text to chunk.
        size: Target chunk size in words.
        overlap: Overlap between chunks in words.

    Returns:
        List of (chunk_text, start_char, end_char) tuples with original text preserved.
    """
    # Build word positions list: [(word, start_pos, end_pos), ...]
    word_positions: list[tuple[str, int, int]] = []
    i = 0
    while i < len(text):
        # Skip whitespace
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        # Find word end
        start = i
        while i < len(text) and not text[i].isspace():
            i += 1
        word_positions.append((text[start:i], start, i))

    if len(word_positions) <= size:
        if len(word_positions) >= MIN_CHUNK_SIZE:
            # Use actual word boundaries, not stripped text
            if word_positions:
                first_start = word_positions[0][1]
                last_end = word_positions[-1][2]
                return [(text[first_start:last_end], first_start, last_end)]
            return [(text, 0, len(text))]
        return []

    # Guard against infinite loop: overlap must be < size
    effective_overlap = min(overlap, size - 1) if size > 1 else 0
    if overlap >= size:
        log.warning(
            "chunk_overlap_too_large",
            message=f"CHUNK_OVERLAP ({overlap}) >= CHUNK_SIZE ({size}), clamping to {effective_overlap}",
        )

    chunks: list[tuple[str, int, int]] = []
    i = 0
    step = max(1, size - effective_overlap)  # Ensure we always advance
    while i < len(word_positions):
        window = word_positions[i : i + size]
        if len(window) >= MIN_CHUNK_SIZE:
            start_char = window[0][1]
            end_char = window[-1][2]
            # Extract original text span (preserves whitespace)
            chunk_text = text[start_char:end_char]
            chunks.append((chunk_text, start_char, end_char))
        i += step

    return chunks


def _build_page_positions(document: ExtractedDocument) -> list[tuple[int, int, int]]:
    """Build a list of (page_num, start_pos, end_pos) for each page.

    Args:
        document: The source document.

    Returns:
        List of tuples mapping page numbers to character positions.
    """
    positions = []
    cumulative = 0
    for page in document.pages:
        start = cumulative
        end = cumulative + len(page.text)
        positions.append((page.page_num, start, end))
        cumulative = end + 1  # +1 for newline separator
    return positions


def _find_page_range_by_position(
    start_pos: int,
    end_pos: int,
    page_positions: list[tuple[int, int, int]],
    document: ExtractedDocument,
) -> tuple[int, int]:
    """Find page range using pre-computed character positions.

    Args:
        start_pos: Start character position in full text.
        end_pos: End character position in full text.
        page_positions: List of (page_num, start, end) tuples.
        document: Source document for fallback.

    Returns:
        Tuple of (page_start, page_end).
    """
    if not page_positions:
        return 1, 1

    page_start = page_positions[0][0]
    page_end = page_positions[-1][0]

    for page_num, p_start, p_end in page_positions:
        if p_start <= start_pos < p_end:
            page_start = page_num
        if p_start < end_pos <= p_end:
            page_end = page_num
            break

    return page_start, max(page_start, page_end)


def chunk_document(
    document: ExtractedDocument,
    provider: str,
    document_version: str | None = None,
) -> list[Chunk]:
    """Chunk a document with full metadata.

    Args:
        document: Extracted document to chunk.
        provider: Provider identifier (e.g., \"cme\").
        document_version: Optional version string detected from document.

    Returns:
        List of Chunk objects with metadata.
    """
    full_text = document.full_text
    sections = split_by_sections(full_text)

    # Build page position map for the full document
    page_positions = _build_page_positions(document)

    chunks: list[Chunk] = []
    chunk_index = 0

    # Track section start offset in full document
    section_offset = 0

    for section_heading, section_text in sections:
        # Find where this section starts in full_text
        section_start = full_text.find(section_text, section_offset)
        if section_start == -1:
            section_start = section_offset  # Fallback

        # Get chunks with character positions relative to section
        text_chunks = window_chunk(section_text)

        for text, rel_start, rel_end in text_chunks:
            # Convert to absolute positions in full document
            abs_start = section_start + rel_start
            abs_end = section_start + rel_end

            page_start, page_end = _find_page_range_by_position(
                abs_start, abs_end, page_positions, document
            )
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
                document_version=document_version,
            )
            chunks.append(chunk)
            chunk_index += 1

        section_offset = section_start + len(section_text)

    return chunks


def save_chunks_artifacts(
    chunks: list[Chunk],
    document_name: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Save chunk artifacts for visibility into the chunking process.

    Creates two files per document:
    - {document_name}.chunks.jsonl: One JSON object per line for each chunk
    - {document_name}.chunks.meta.json: Summary metadata about the chunking

    Args:
        chunks: List of chunks from the document.
        document_name: Original document filename.
        output_dir: Directory to save artifacts (e.g., data/chunks/cme/).

    Returns:
        Tuple of (chunks_path, meta_path) for saved files.
    """
    import json
    from datetime import datetime
    from datetime import timezone

    output_dir.mkdir(parents=True, exist_ok=True)

    # Derive base filename (without extension)
    base_name = Path(document_name).stem

    # Save chunks as JSONL (one chunk per line for easy inspection)
    chunks_path = output_dir / f"{base_name}.chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            chunk_data = {
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "section_heading": chunk.section_heading,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "word_count": chunk.word_count,
                "is_definitions": chunk.is_definitions,
                "text_preview": chunk.text[:200] + "..."
                if len(chunk.text) > 200
                else chunk.text,
                "text": chunk.text,
            }
            f.write(json.dumps(chunk_data) + "\n")

    # Save chunking summary metadata
    meta_path = output_dir / f"{base_name}.chunks.meta.json"
    total_words = sum(c.word_count for c in chunks)
    pages_covered: set[int] = set()
    for c in chunks:
        pages_covered.update(range(c.page_start, c.page_end + 1))

    metadata = {
        "document_name": document_name,
        "chunked_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": len(chunks),
        "total_words": total_words,
        "avg_words_per_chunk": round(total_words / len(chunks), 1) if chunks else 0,
        "pages_covered": sorted(pages_covered),
        "sections": sorted({c.section_heading for c in chunks}),
        "definition_chunks": sum(1 for c in chunks if c.is_definitions),
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return chunks_path, meta_path
