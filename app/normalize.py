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

# Leading phrases to strip (case-insensitive)
LEADING_PHRASES = [
    r"^what\s+(is|are|was|were)\s+",
    r"^can\s+you\s+(tell\s+me|explain|describe)\s+",
    r"^could\s+you\s+(tell\s+me|explain|describe)\s+",
    r"^please\s+(tell\s+me|explain|describe)\s+",
    r"^i\s+(want|need)\s+to\s+know\s+",
    r"^tell\s+me\s+(about\s+)?",
    r"^explain\s+(to\s+me\s+)?",
    r"^describe\s+",
    r"^show\s+me\s+",
    r"^where\s+(can\s+i\s+find|is)\s+",
    r"^how\s+(do|does|can)\s+",
]

# Filler words to remove (but preserve in context of meaningful phrases)
FILLER_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "am",
    "be",
    "been",
    "being",
    "of",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "by",
    "from",
    "about",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
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


def normalize_query(query: str) -> str:
    """Normalize a query for improved retrieval.

    Performs the following transformations:
    1. Strip leading conversational phrases
    2. Convert to lowercase
    3. Remove filler words while preserving domain terms
    4. Preserve multi-word phrases and hyphens
    5. Clean up whitespace

    Args:
        query: Raw user query string.

    Returns:
        Normalized query string optimized for retrieval.

    Examples:
        >>> normalize_query("What is the fee schedule?")
        'fee schedule'
        >>> normalize_query("Can you tell me about real-time data fees?")
        'real-time data fees'
        >>> normalize_query("Where can I find the CME exhibit?")
        'cme exhibit'
    """
    if not query or not query.strip():
        return ""

    original = query
    normalized = query.strip()

    # 1. Strip leading conversational phrases
    for pattern in LEADING_PHRASES:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

    # 2. Convert to lowercase for processing
    normalized = normalized.lower()

    # 3. Preserve hyphenated terms (e.g., "real-time", "non-professional")
    # Replace hyphens with placeholder to prevent splitting
    hyphen_placeholder = "___HYPHEN___"
    normalized = normalized.replace("-", hyphen_placeholder)

    # 4. Tokenize and filter
    words = normalized.split()
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

    # 5. Join and clean up whitespace
    normalized = " ".join(filtered_words).strip()

    # Log normalization if significant change
    if normalized != original.lower().strip():
        log.debug(
            "query_normalized",
            original=original,
            normalized=normalized,
            removed_words=len(words) - len(filtered_words),
        )

    return normalized
