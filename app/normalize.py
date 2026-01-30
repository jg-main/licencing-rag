# app/normalize.py
"""Query normalization for improved retrieval.

This module provides query preprocessing to improve both vector and keyword search:
- Strips conversational phrases ("what is", "can you tell me")
- Removes filler words (a, an, the, is, are, etc.)
- Preserves domain-specific terms and nouns
- Handles legal/financial terminology

The goal is to extract the core semantic content for better embedding similarity
and BM25 keyword matching.
"""

import re

from app.logging import get_logger

log = get_logger(__name__)

# Leading phrases to strip (exact match from spec v0.4)
# Must match spec exactly for acceptance criteria
STRIP_PREFIXES = [
    "what is",
    "what are",
    "what's",
    "can you",
    "could you",
    "would you",
    "please explain",
    "please tell me",
    "how does",
    "how do",
    "how is",
    "tell me about",
    "explain",
]

# Filler words to remove (from spec v0.4 + prepositions inferred from examples)
# Must match spec exactly for acceptance criteria
FILLER_WORDS = {
    # Articles
    "the",
    "a",
    "an",
    # Auxiliary verbs
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    # Modal verbs
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    # Demonstratives
    "this",
    "that",
    "these",
    "those",
    # Pronouns
    "i",
    "me",
    "my",
    "we",
    "our",
    "you",
    "your",
    # Common prepositions (inferred from spec examples)
    "for",
    "of",
    "in",
    "on",
    "at",
    "to",
    "from",
    "with",
    "about",
    "by",
    # Action verbs that are conversational filler (inferred from spec examples)
    "explain",
    "tell",
}

# Domain-specific terms to preserve (never remove these words)
PRESERVE_TERMS = {
    "fee",
    "fees",
    "rate",
    "rates",
    "price",
    "pricing",
    "cost",
    "costs",
    "charge",
    "charges",
    "schedule",
    "schedules",
    "exhibit",
    "exhibits",
    "table",
    "tables",
    "section",
    "sections",
    "clause",
    "clauses",
    "term",
    "terms",
    "condition",
    "conditions",
    "agreement",
    "agreements",
    "contract",
    "contracts",
    "license",
    "licenses",
    "vendor",
    "vendors",
    "subscriber",
    "subscribers",
    "data",
    "information",
    "market",
    "real-time",
    "delayed",
    "historical",
    "professional",
    "non-professional",
    "redistribution",
    "display",
    "internal",
    "external",
    "commercial",
    "usage",
    "use",
    "rights",
    "entitlement",
    "entitlements",
}


def extract_year_from_query(query: str) -> int | None:
    """Extract a year reference from a query for temporal filtering.

    Looks for 4-digit years in the query. Returns the year if found,
    particularly useful for fee-related queries where document freshness matters.

    Args:
        query: Raw user query string.

    Returns:
        Year as integer if found, None otherwise.

    Examples:
        >>> extract_year_from_query("What are the 2026 fees?")
        2026
        >>> extract_year_from_query("January 2025 fee schedule")
        2025
        >>> extract_year_from_query("What is the display device fee?")
        None
    """
    # Look for 4-digit year pattern (1990-2099 range for broad source compatibility)
    # Covers historical documents (1990s) through future schedules (2090s)
    year_pattern = r"\b(19[9][0-9]|20[0-9]{2})\b"
    match = re.search(year_pattern, query)
    if match:
        year = int(match.group(1))
        log.debug("year_extracted_from_query", query=query[:50], year=year)
        return year
    return None


def normalize_query(query: str) -> str:
    """Normalize a query for improved retrieval.

    Follows spec v0.4 algorithm:
    1. Lowercase
    2. Strip leading phrases (exact prefix match)
    3. Remove filler words
    4. Preserve nouns and legal terms (implicitly via PRESERVE_TERMS)

    Args:
        query: Raw user query string.

    Returns:
        Normalized query string optimized for retrieval.

    Examples:
        >>> normalize_query("What is the fee schedule?")
        'fee schedule'
        >>> normalize_query("Can you explain redistribution requirements?")
        'redistribution requirements'
        >>> normalize_query("How does CME charge for real-time data?")
        'cme charge real-time data'
    """
    if not query or not query.strip():
        return ""

    original = query
    # Normalize whitespace: lowercase, strip, and collapse multiple spaces
    text = " ".join(query.lower().split())

    # 1. Strip prefix phrases (exact match)
    for prefix in STRIP_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break  # Only strip first matching prefix

    # 2. Preserve hyphenated terms (e.g., "real-time", "non-professional")
    # Replace hyphens with placeholder to prevent splitting
    hyphen_placeholder = "___HYPHEN___"
    text = text.replace("-", hyphen_placeholder)

    # 3. Tokenize and filter
    words = text.split()
    filtered_words = []

    for word in words:
        # Restore hyphens
        word = word.replace(hyphen_placeholder, "-")

        # Remove punctuation except hyphens
        word_clean = re.sub(r"[^\w\-]", "", word)

        if not word_clean:
            continue

        # Preserve domain-specific terms
        if word_clean in PRESERVE_TERMS:
            filtered_words.append(word_clean)
        # Keep words not in filler list
        elif word_clean not in FILLER_WORDS:
            filtered_words.append(word_clean)
        # Keep numbers
        elif word_clean.isdigit():
            filtered_words.append(word_clean)

    # 4. Join and clean up whitespace
    normalized = " ".join(filtered_words).strip()

    # Log normalization if significant change
    if normalized != original.lower().strip():
        log.debug(
            "query_normalized",
            original=original,
            normalized=normalized,
            words_removed=len(words) - len(filtered_words),
        )

    return normalized
