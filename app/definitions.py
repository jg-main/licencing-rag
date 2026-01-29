# app/definitions.py
"""Definitions auto-linking for the License Intelligence System.

This module provides functionality to:
- Extract defined terms from text (quoted terms, initial caps terms)
- Build and persist a definitions index from definition chunks
- Retrieve relevant definitions for terms found in query responses
- Cache definitions to reduce redundant retrievals

The definitions index maps normalized term keys to chunk IDs containing
the definition. During query processing, terms in the LLM response are
extracted and their definitions are automatically included.
"""

import pickle
import re
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.logging import get_logger

log = get_logger(__name__)

# Definitions index storage directory
DEFINITIONS_INDEX_DIR = Path("index/definitions")

# Index format version for compatibility checking
DEFINITIONS_INDEX_VERSION = "1.0"

# Magic bytes to identify valid index files
DEFINITIONS_INDEX_MAGIC = b"DEFIDX01"

# Common legal/licensing terms that should trigger definition lookup
# These are terms frequently defined in market data license agreements
COMMON_DEFINED_TERMS = frozenset(
    {
        "subscriber",
        "vendor",
        "distributor",
        "derived data",
        "real-time",
        "delayed",
        "non-display",
        "display",
        "professional",
        "non-professional",
        "redistribution",
        "information",
        "market data",
        "data",
        "licensee",
        "licensor",
        "user",
        "device",
        "internal use",
        "external use",
        "controlled affiliate",
        "affiliate",
        "authorized recipient",
        "end user",
        "fee",
        "benchmark",
        "index",
        "intellectual property",
        "confidential information",
        "territory",
        "term",
        "effective date",
        "termination",
    }
)

# Pattern to extract quoted terms like "Subscriber" or 'Derived Data'
QUOTED_TERM_PATTERN = re.compile(r'["\']([^"\']{2,50})["\']')

# Pattern to detect initial caps terms (likely defined terms)
# Matches 2-5 word phrases where each word starts with uppercase
INITIAL_CAPS_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")


@dataclass
class DefinitionEntry:
    """A definition entry linking a term to its source."""

    term: str  # Original term as found in the document
    normalized_term: str  # Lowercase, normalized for matching
    chunk_id: str  # ID of the chunk containing this definition
    document_name: str
    document_path: str
    section_heading: str
    page_start: int
    page_end: int
    definition_text: str  # The actual definition text (excerpt)
    source: str = ""  # Provider identifier (e.g., "cme", "cta_utp")


@dataclass
class DefinitionsIndex:
    """Index mapping terms to their definitions.

    Stores term -> [DefinitionEntry] mappings for quick lookup.
    Multiple definitions for the same term are supported (from different docs).
    """

    source: str
    version: str = DEFINITIONS_INDEX_VERSION
    entries: dict[str, list[DefinitionEntry]] = field(default_factory=dict)
    chunk_id_to_terms: dict[str, list[str]] = field(default_factory=dict)

    def add_entry(self, entry: DefinitionEntry) -> None:
        """Add a definition entry to the index.

        Args:
            entry: The definition entry to add.
        """
        key = entry.normalized_term
        if key not in self.entries:
            self.entries[key] = []
        self.entries[key].append(entry)

        # Track reverse mapping for chunk-based lookups
        if entry.chunk_id not in self.chunk_id_to_terms:
            self.chunk_id_to_terms[entry.chunk_id] = []
        if key not in self.chunk_id_to_terms[entry.chunk_id]:
            self.chunk_id_to_terms[entry.chunk_id].append(key)

    def get_definitions(self, term: str) -> list[DefinitionEntry]:
        """Get all definitions for a term.

        Args:
            term: Term to look up (case-insensitive).

        Returns:
            List of DefinitionEntry objects, empty if not found.
        """
        return self.entries.get(normalize_term(term), [])

    def has_term(self, term: str) -> bool:
        """Check if a term has any definitions.

        Args:
            term: Term to check.

        Returns:
            True if the term has at least one definition.
        """
        return normalize_term(term) in self.entries

    def get_all_terms(self) -> list[str]:
        """Get all indexed terms.

        Returns:
            List of normalized terms.
        """
        return list(self.entries.keys())

    def __len__(self) -> int:
        """Return the number of unique terms indexed."""
        return len(self.entries)


def normalize_term(term: str) -> str:
    """Normalize a term for consistent matching.

    Args:
        term: Term to normalize.

    Returns:
        Normalized term (lowercase, stripped, single spaces).
    """
    # Lowercase, strip whitespace, normalize multiple spaces
    normalized = " ".join(term.lower().split())
    return normalized


def extract_quoted_terms(text: str) -> list[str]:
    """Extract terms in quotes from text.

    Finds terms enclosed in single or double quotes that are likely
    defined terms being referenced.

    Args:
        text: Text to search for quoted terms.

    Returns:
        List of extracted terms (not normalized).
    """
    matches = QUOTED_TERM_PATTERN.findall(text)
    # Filter out common non-definition quoted strings
    filtered = []
    for match in matches:
        # Skip if it's a URL, file path, or code-like string
        if "/" in match or "\\" in match or "." in match.split()[-1]:
            continue
        # Skip if it's all lowercase (likely not a defined term)
        if match.islower() and match not in ["subscriber", "vendor", "user"]:
            continue
        filtered.append(match)
    return filtered


def extract_initial_caps_terms(text: str) -> list[str]:
    """Extract initial caps terms that might be defined terms.

    Finds terms like "Derived Data", "Controlled Affiliate" that
    are commonly used as defined terms in legal documents.

    Args:
        text: Text to search for initial caps terms.

    Returns:
        List of extracted terms (not normalized).
    """
    matches = INITIAL_CAPS_PATTERN.findall(text)
    # Filter to likely defined terms
    filtered = []
    for match in matches:
        normalized = normalize_term(match)
        # Check if it's a known defined term pattern
        if normalized in COMMON_DEFINED_TERMS:
            filtered.append(match)
        # Or if it's a multi-word capitalized phrase (likely defined)
        elif " " in match and len(match.split()) >= 2:
            # Skip common English phrases that aren't definitions
            if normalized not in {
                "the agreement",
                "this agreement",
                "the parties",
                "each party",
            }:
                filtered.append(match)
    return filtered


def extract_defined_terms(text: str) -> list[str]:
    """Extract all potential defined terms from text.

    Combines quoted term extraction and initial caps detection.

    Args:
        text: Text to extract terms from.

    Returns:
        List of unique terms found (not normalized).
    """
    terms = set()

    # Extract quoted terms
    for term in extract_quoted_terms(text):
        terms.add(term)

    # Extract initial caps terms
    for term in extract_initial_caps_terms(text):
        terms.add(term)

    return list(terms)


def extract_definition_from_chunk(
    chunk_text: str,
    term: str,
) -> str | None:
    """Extract the definition text for a term from a chunk.

    Looks for patterns like:
    - "Term" means ...
    - "Term" shall mean ...
    - "Term": ...
    - Term means ...

    Args:
        chunk_text: Text of the chunk containing definitions.
        term: Term to find the definition for.

    Returns:
        The definition text, or None if not found.
    """
    # Escape special regex characters in the term
    escaped_term = re.escape(term)

    # Patterns to match definition text
    patterns = [
        # "Term" means/shall mean ...
        rf'["\']?{escaped_term}["\']?\s+(?:shall\s+)?means?\s+(.{{10,500}}?)(?:\.|;|\n\n)',
        # "Term": definition
        rf'["\']?{escaped_term}["\']?\s*:\s*(.{{10,500}}?)(?:\.|;|\n\n)',
        # Term - definition
        rf'["\']?{escaped_term}["\']?\s*[-–—]\s*(.{{10,500}}?)(?:\.|;|\n\n)',
    ]

    for pattern in patterns:
        match = re.search(pattern, chunk_text, re.IGNORECASE | re.DOTALL)
        if match:
            definition = match.group(1).strip()
            # Clean up the definition
            definition = " ".join(definition.split())  # Normalize whitespace
            return definition

    return None


def build_definitions_index(
    source: str,
    chunks: list[dict[str, Any]],
) -> DefinitionsIndex:
    """Build a definitions index from chunks.

    Scans all chunks marked as definitions sections and extracts
    term-definition mappings.

    Args:
        source: Provider identifier.
        chunks: List of chunk dictionaries with text and metadata.

    Returns:
        DefinitionsIndex with all extracted definitions.
    """
    index = DefinitionsIndex(source=source)

    for chunk in chunks:
        metadata = chunk.get("metadata", {})

        # Only process definition chunks
        if not metadata.get("is_definitions", False):
            continue

        chunk_text = chunk.get("text", "")
        chunk_id = metadata.get("chunk_id", "")

        # Extract potential terms from the chunk
        potential_terms = extract_defined_terms(chunk_text)

        # Also check for common defined terms that might not be capitalized
        for common_term in COMMON_DEFINED_TERMS:
            if common_term in chunk_text.lower():
                # Check if there's actually a definition for it
                definition = extract_definition_from_chunk(chunk_text, common_term)
                if definition:
                    potential_terms.append(common_term)

        # Try to extract definitions for each term
        for term in potential_terms:
            definition = extract_definition_from_chunk(chunk_text, term)
            if definition:
                entry = DefinitionEntry(
                    term=term,
                    normalized_term=normalize_term(term),
                    chunk_id=chunk_id,
                    document_name=metadata.get("document_name", "Unknown"),
                    document_path=metadata.get("document_path", "Unknown"),
                    section_heading=metadata.get("section_heading", "Definitions"),
                    page_start=metadata.get("page_start", 1),
                    page_end=metadata.get("page_end", 1),
                    definition_text=definition,
                    source=source,
                )
                index.add_entry(entry)
                log.debug(
                    "extracted_definition",
                    term=term,
                    chunk_id=chunk_id,
                    definition_length=len(definition),
                )

    log.info(
        "definitions_index_built",
        source=source,
        terms=len(index),
        total_entries=sum(len(v) for v in index.entries.values()),
    )

    return index


def save_definitions_index(index: DefinitionsIndex) -> Path:
    """Save a definitions index to disk.

    Args:
        index: DefinitionsIndex to save.

    Returns:
        Path to the saved index file.

    Security Note:
        Uses pickle for serialization. Only load indexes from trusted sources.
    """
    DEFINITIONS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index_path = DEFINITIONS_INDEX_DIR / f"{index.source}_definitions.pkl"

    with open(index_path, "wb") as f:
        f.write(DEFINITIONS_INDEX_MAGIC)
        pickle.dump(index, f)

    log.info("definitions_index_saved", path=str(index_path), terms=len(index))
    return index_path


def load_definitions_index(source: str) -> DefinitionsIndex | None:
    """Load a definitions index from disk.

    Args:
        source: Provider identifier.

    Returns:
        DefinitionsIndex if found and valid, None otherwise.

    Security Note:
        Uses pickle for deserialization. Only load indexes from trusted sources.
    """
    index_path = DEFINITIONS_INDEX_DIR / f"{source}_definitions.pkl"

    if not index_path.exists():
        log.debug("definitions_index_not_found", source=source)
        return None

    try:
        with open(index_path, "rb") as f:
            magic = f.read(len(DEFINITIONS_INDEX_MAGIC))
            if magic != DEFINITIONS_INDEX_MAGIC:
                log.warning(
                    "definitions_index_invalid_magic",
                    source=source,
                    path=str(index_path),
                )
                return None

            index = pickle.load(f)  # noqa: S301 - trusted local file

            if not isinstance(index, DefinitionsIndex):
                log.warning(
                    "definitions_index_invalid_type",
                    source=source,
                    actual_type=type(index).__name__,
                )
                return None

            log.debug("definitions_index_loaded", source=source, terms=len(index))
            return index

    except (pickle.UnpicklingError, EOFError) as e:
        log.warning(
            "definitions_index_load_failed",
            source=source,
            error=str(e),
        )
        return None


class DefinitionsRetriever:
    """Retrieves definitions for terms found in query responses.

    Provides caching and batch retrieval to minimize redundant lookups.
    """

    def __init__(self, sources: list[str]) -> None:
        """Initialize the retriever for specified sources.

        Args:
            sources: List of source identifiers to load indexes for.
        """
        self.sources = sources
        self.indexes: dict[str, DefinitionsIndex] = {}
        self._cache: dict[str, list[DefinitionEntry]] = {}

        # Load indexes for all sources
        for source in sources:
            index = load_definitions_index(source)
            if index:
                self.indexes[source] = index
                log.debug("loaded_definitions_index", source=source)

    def get_definition(
        self,
        term: str,
        source: str | None = None,
    ) -> list[DefinitionEntry]:
        """Get definitions for a term.

        Args:
            term: Term to look up.
            source: Optional source to limit search to.

        Returns:
            List of DefinitionEntry objects.
        """
        cache_key = f"{source or 'all'}:{normalize_term(term)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        results: list[DefinitionEntry] = []

        if source:
            if source in self.indexes:
                results = self.indexes[source].get_definitions(term)
        else:
            for idx in self.indexes.values():
                results.extend(idx.get_definitions(term))

        self._cache[cache_key] = results
        return results

    def get_definitions_for_terms(
        self,
        terms: list[str],
        source: str | None = None,
    ) -> dict[str, list[DefinitionEntry]]:
        """Get definitions for multiple terms.

        Args:
            terms: List of terms to look up.
            source: Optional source to limit search to.

        Returns:
            Dictionary mapping normalized terms to their definitions.
        """
        results: dict[str, list[DefinitionEntry]] = {}

        for term in terms:
            definitions = self.get_definition(term, source)
            if definitions:
                results[normalize_term(term)] = definitions

        return results

    def find_definitions_in_text(
        self,
        text: str,
        source: str | None = None,
        max_definitions: int = 10,
    ) -> dict[str, list[DefinitionEntry]]:
        """Find and retrieve definitions for terms mentioned in text.

        Scans the text for potential defined terms and retrieves
        their definitions from the index.

        Args:
            text: Text to scan for defined terms.
            source: Optional source to limit search to.
            max_definitions: Maximum number of definitions to return.

        Returns:
            Dictionary mapping normalized terms to their definitions.
        """
        # Extract potential terms from the text
        terms = extract_defined_terms(text)

        # Also check for common defined terms
        text_lower = text.lower()
        for common_term in COMMON_DEFINED_TERMS:
            if common_term in text_lower:
                terms.append(common_term)

        # Deduplicate while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            normalized = normalize_term(term)
            if normalized not in seen:
                seen.add(normalized)
                unique_terms.append(term)

        # Get definitions for each term
        results = self.get_definitions_for_terms(unique_terms, source)

        # Limit total definitions
        if len(results) > max_definitions:
            # Keep the first max_definitions entries
            limited: dict[str, list[DefinitionEntry]] = {}
            for i, (key, value) in enumerate(results.items()):
                if i >= max_definitions:
                    break
                limited[key] = value
            results = limited

        return results

    def clear_cache(self) -> None:
        """Clear the definition cache."""
        self._cache.clear()


def format_definitions_for_context(
    definitions: dict[str, list[DefinitionEntry]],
) -> str:
    """Format definitions for inclusion in LLM context.

    Args:
        definitions: Dictionary of term -> definition entries.

    Returns:
        Formatted string for context injection.
    """
    if not definitions:
        return ""

    lines = ["--- DEFINITIONS ---"]

    for term, entries in definitions.items():
        # Use the first definition (usually the most authoritative)
        entry = entries[0]
        provider_upper = entry.source.upper() if entry.source else "UNKNOWN"
        page_info = (
            f"Page {entry.page_start}"
            if entry.page_start == entry.page_end
            else f"Pages {entry.page_start}–{entry.page_end}"
        )
        lines.append(f'"{entry.term}": {entry.definition_text}')
        lines.append(
            f"  — [{provider_upper}] {entry.document_name}, {entry.section_heading} ({page_info})"
        )

    lines.append("--- END DEFINITIONS ---")
    return "\n".join(lines)


def format_definitions_for_output(
    definitions: dict[str, list[DefinitionEntry]],
) -> list[dict[str, Any]]:
    """Format definitions for JSON output.

    Args:
        definitions: Dictionary of term -> definition entries.

    Returns:
        List of definition dictionaries for JSON serialization.
    """
    result = []

    for term, entries in definitions.items():
        for entry in entries:
            result.append(
                {
                    "term": entry.term,
                    "definition": entry.definition_text,
                    "document": entry.document_name,
                    "document_path": entry.document_path,
                    "section": entry.section_heading,
                    "page_start": entry.page_start,
                    "page_end": entry.page_end,
                    "source": entry.source,
                }
            )

    return result


@lru_cache(maxsize=16)
def get_definitions_retriever(providers_tuple: tuple[str, ...]) -> DefinitionsRetriever:
    """Get or create a cached DefinitionsRetriever.

    Uses LRU cache to avoid reloading indexes for repeated queries.

    Args:
        providers_tuple: Tuple of source identifiers (must be hashable).

    Returns:
        DefinitionsRetriever instance.
    """
    return DefinitionsRetriever(list(providers_tuple))
