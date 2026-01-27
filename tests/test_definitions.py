"""Tests for definitions auto-linking implementation."""

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.definitions import COMMON_DEFINED_TERMS
from app.definitions import DefinitionEntry
from app.definitions import DefinitionsIndex
from app.definitions import DefinitionsRetriever
from app.definitions import build_definitions_index
from app.definitions import extract_defined_terms
from app.definitions import extract_definition_from_chunk
from app.definitions import extract_initial_caps_terms
from app.definitions import extract_quoted_terms
from app.definitions import format_definitions_for_context
from app.definitions import format_definitions_for_output
from app.definitions import load_definitions_index
from app.definitions import normalize_term
from app.definitions import save_definitions_index


class TestNormalizeTerm:
    """Tests for term normalization."""

    def test_basic_normalization(self) -> None:
        """Basic text is normalized correctly."""
        assert normalize_term("Subscriber") == "subscriber"

    def test_multiple_spaces(self) -> None:
        """Multiple spaces are collapsed."""
        assert normalize_term("Derived   Data") == "derived data"

    def test_leading_trailing_whitespace(self) -> None:
        """Whitespace is stripped."""
        assert normalize_term("  Vendor  ") == "vendor"

    def test_mixed_case(self) -> None:
        """Mixed case is lowercased."""
        assert normalize_term("NON-DISPLAY UsAgE") == "non-display usage"


class TestExtractQuotedTerms:
    """Tests for quoted term extraction."""

    def test_double_quotes(self) -> None:
        """Extracts terms in double quotes."""
        text = 'The "Subscriber" must comply with "Data Usage" terms.'
        terms = extract_quoted_terms(text)
        assert "Subscriber" in terms
        assert "Data Usage" in terms

    def test_single_quotes(self) -> None:
        """Extracts terms in single quotes."""
        text = "The 'Vendor' must provide 'Market Data' as defined."
        terms = extract_quoted_terms(text)
        assert "Vendor" in terms
        assert "Market Data" in terms

    def test_filters_urls(self) -> None:
        """Filters out URL-like strings."""
        text = 'See "https://example.com/path" for details.'
        terms = extract_quoted_terms(text)
        assert len(terms) == 0

    def test_filters_file_paths(self) -> None:
        """Filters out file path-like strings."""
        text = 'Save to "/path/to/file.txt" location.'
        terms = extract_quoted_terms(text)
        assert len(terms) == 0

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        terms = extract_quoted_terms("")
        assert terms == []

    def test_no_quotes(self) -> None:
        """Text without quotes returns empty list."""
        terms = extract_quoted_terms("No quoted terms here.")
        assert terms == []


class TestExtractInitialCapsTerms:
    """Tests for initial caps term extraction."""

    def test_known_defined_term(self) -> None:
        """Extracts known defined terms with context."""
        text = "The Subscriber must comply with the agreement."
        terms = extract_initial_caps_terms(text)
        # May include article prefix like "The Subscriber"
        normalized = [normalize_term(t) for t in terms]
        assert any("subscriber" in n for n in normalized)

    def test_multi_word_defined_term(self) -> None:
        """Extracts multi-word defined terms with context."""
        text = "All Derived Data must be reported."
        terms = extract_initial_caps_terms(text)
        # May include leading article like "All Derived Data"
        normalized = [normalize_term(t) for t in terms]
        assert any("derived data" in n for n in normalized)

    def test_filters_common_phrases(self) -> None:
        """Filters out common non-definition phrases."""
        text = "The Agreement between The Parties."
        terms = extract_initial_caps_terms(text)
        # Should not include "The Parties" or "The Agreement"
        for term in terms:
            assert normalize_term(term) not in {"the parties", "the agreement"}


class TestExtractDefinedTerms:
    """Tests for combined term extraction."""

    def test_combines_quoted_and_caps(self) -> None:
        """Combines both extraction methods."""
        text = 'The "Subscriber" and Derived Data must comply.'
        terms = extract_defined_terms(text)
        # Should find both quoted and caps terms
        normalized = {normalize_term(t) for t in terms}
        assert "subscriber" in normalized

    def test_deduplicates(self) -> None:
        """Returns unique terms only."""
        text = '"Subscriber" is a Subscriber who uses "Subscriber" services.'
        terms = extract_defined_terms(text)
        # Check we don't have duplicates
        normalized = [normalize_term(t) for t in terms]
        assert normalized.count("subscriber") <= 1


class TestExtractDefinitionFromChunk:
    """Tests for definition extraction from chunk text."""

    def test_means_pattern(self) -> None:
        """Extracts definition using 'means' pattern."""
        chunk = '"Subscriber" means any person or entity receiving Information.'
        definition = extract_definition_from_chunk(chunk, "Subscriber")
        assert definition is not None
        assert "person or entity" in definition

    def test_shall_mean_pattern(self) -> None:
        """Extracts definition using 'shall mean' pattern."""
        chunk = '"Vendor" shall mean a company that redistributes data.'
        definition = extract_definition_from_chunk(chunk, "Vendor")
        assert definition is not None
        assert "company" in definition

    def test_colon_pattern(self) -> None:
        """Extracts definition using colon pattern."""
        chunk = '"Fee": the amount payable for data access.'
        definition = extract_definition_from_chunk(chunk, "Fee")
        assert definition is not None
        assert "amount payable" in definition

    def test_no_definition_found(self) -> None:
        """Returns None when no definition pattern matches."""
        chunk = "This chunk mentions Subscriber but doesn't define it."
        definition = extract_definition_from_chunk(chunk, "Subscriber")
        assert definition is None

    def test_case_insensitive(self) -> None:
        """Definition extraction is case-insensitive."""
        chunk = '"subscriber" MEANS any person receiving data.'
        definition = extract_definition_from_chunk(chunk, "Subscriber")
        assert definition is not None


class TestDefinitionsIndex:
    """Tests for DefinitionsIndex class."""

    def test_add_and_get_entry(self) -> None:
        """Can add and retrieve definition entries."""
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        definitions = index.get_definitions("Subscriber")
        assert len(definitions) == 1
        assert definitions[0].term == "Subscriber"

    def test_case_insensitive_lookup(self) -> None:
        """Lookup is case-insensitive."""
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        # All case variations should work
        assert len(index.get_definitions("subscriber")) == 1
        assert len(index.get_definitions("SUBSCRIBER")) == 1
        assert len(index.get_definitions("Subscriber")) == 1

    def test_has_term(self) -> None:
        """has_term returns correct boolean."""
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        assert index.has_term("Subscriber")
        assert index.has_term("subscriber")
        assert not index.has_term("Vendor")

    def test_len(self) -> None:
        """Length returns number of unique terms."""
        index = DefinitionsIndex(provider="test")
        assert len(index) == 0

        entry1 = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry1)
        assert len(index) == 1

        # Adding same term again doesn't increase count
        entry2 = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_2",
            document_name="other.pdf",
            document_path="other.pdf",
            section_heading="Definitions",
            page_start=5,
            page_end=5,
            definition_text="Another definition.",
            provider="test",
        )
        index.add_entry(entry2)
        assert len(index) == 1  # Same term, still just one unique term

    def test_get_all_terms(self) -> None:
        """get_all_terms returns all indexed terms."""
        index = DefinitionsIndex(provider="test")
        entry1 = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        entry2 = DefinitionEntry(
            term="Vendor",
            normalized_term="vendor",
            chunk_id="test_doc_2",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=2,
            page_end=2,
            definition_text="A data provider.",
            provider="test",
        )
        index.add_entry(entry1)
        index.add_entry(entry2)

        terms = index.get_all_terms()
        assert "subscriber" in terms
        assert "vendor" in terms


class TestBuildDefinitionsIndex:
    """Tests for building definitions index from chunks."""

    def test_builds_from_definition_chunks(self) -> None:
        """Builds index from chunks marked as definitions."""
        chunks = [
            {
                "text": '"Subscriber" means any person or entity receiving Information.',
                "metadata": {
                    "chunk_id": "cme_doc_1",
                    "is_definitions": True,
                    "document_name": "agreement.pdf",
                    "document_path": "agreement.pdf",
                    "section_heading": "Definitions",
                    "page_start": 5,
                    "page_end": 5,
                },
            },
            {
                "text": "This is regular content about subscribers.",
                "metadata": {
                    "chunk_id": "cme_doc_2",
                    "is_definitions": False,
                    "document_name": "agreement.pdf",
                    "document_path": "agreement.pdf",
                    "section_heading": "Section 1",
                    "page_start": 10,
                    "page_end": 10,
                },
            },
        ]

        index = build_definitions_index("cme", chunks)
        assert index.has_term("Subscriber")

    def test_ignores_non_definition_chunks(self) -> None:
        """Ignores chunks not marked as definitions."""
        chunks = [
            {
                "text": '"Vendor" means a data provider.',
                "metadata": {
                    "chunk_id": "cme_doc_1",
                    "is_definitions": False,  # Not a definition chunk
                    "document_name": "agreement.pdf",
                    "document_path": "agreement.pdf",
                    "section_heading": "Section 1",
                    "page_start": 10,
                    "page_end": 10,
                },
            },
        ]

        index = build_definitions_index("cme", chunks)
        # Even though text has definition pattern, chunk isn't marked as definitions
        assert len(index) == 0


class TestSaveLoadDefinitionsIndex:
    """Tests for saving and loading definitions index."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Can save and load index correctly."""
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        # Mock the index directory
        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            save_definitions_index(index)
            loaded = load_definitions_index("test")

        assert loaded is not None
        assert len(loaded) == 1
        assert loaded.has_term("Subscriber")

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Loading non-existent index returns None."""
        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            loaded = load_definitions_index("nonexistent")
        assert loaded is None


class TestDefinitionsRetriever:
    """Tests for DefinitionsRetriever class."""

    def test_get_definition(self, tmp_path: Path) -> None:
        """Can retrieve definitions for a term."""
        # Create and save an index
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            save_definitions_index(index)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            retriever = DefinitionsRetriever(["test"])
            definitions = retriever.get_definition("Subscriber")

        assert len(definitions) == 1
        assert definitions[0].term == "Subscriber"

    def test_find_definitions_in_text(self, tmp_path: Path) -> None:
        """Finds definitions for terms mentioned in text."""
        # Create and save an index
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            save_definitions_index(index)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            retriever = DefinitionsRetriever(["test"])
            text = "The Subscriber must comply with data usage rules."
            definitions = retriever.find_definitions_in_text(text)

        assert "subscriber" in definitions

    def test_caching(self, tmp_path: Path) -> None:
        """Caches definition lookups."""
        index = DefinitionsIndex(provider="test")
        entry = DefinitionEntry(
            term="Subscriber",
            normalized_term="subscriber",
            chunk_id="test_doc_1",
            document_name="test.pdf",
            document_path="test.pdf",
            section_heading="Definitions",
            page_start=1,
            page_end=1,
            definition_text="A person receiving data.",
            provider="test",
        )
        index.add_entry(entry)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            save_definitions_index(index)

        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            retriever = DefinitionsRetriever(["test"])

            # First call populates cache
            result1 = retriever.get_definition("Subscriber")
            # Second call should use cache
            result2 = retriever.get_definition("Subscriber")

            assert result1 == result2
            assert len(retriever._cache) > 0

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Can clear the cache."""
        with patch("app.definitions.DEFINITIONS_INDEX_DIR", tmp_path):
            retriever = DefinitionsRetriever([])
            retriever._cache["test"] = []
            assert len(retriever._cache) == 1

            retriever.clear_cache()
            assert len(retriever._cache) == 0


class TestFormatDefinitionsForContext:
    """Tests for formatting definitions for LLM context."""

    def test_formats_definitions(self) -> None:
        """Formats definitions correctly with provider and page info."""
        definitions = {
            "subscriber": [
                DefinitionEntry(
                    term="Subscriber",
                    normalized_term="subscriber",
                    chunk_id="test_doc_1",
                    document_name="test.pdf",
                    document_path="Agreements/test.pdf",
                    section_heading="Definitions",
                    page_start=1,
                    page_end=1,
                    definition_text="A person receiving data.",
                    provider="cme",
                )
            ]
        }

        result = format_definitions_for_context(definitions)

        assert "DEFINITIONS" in result
        assert "Subscriber" in result
        assert "A person receiving data" in result
        assert "[CME]" in result  # Provider in uppercase
        assert "test.pdf" in result  # Document name
        assert "Page 1" in result  # Page info

    def test_empty_definitions(self) -> None:
        """Returns empty string for empty definitions."""
        result = format_definitions_for_context({})
        assert result == ""


class TestFormatDefinitionsForOutput:
    """Tests for formatting definitions for JSON output."""

    def test_formats_for_json(self) -> None:
        """Formats definitions for JSON output."""
        definitions = {
            "subscriber": [
                DefinitionEntry(
                    term="Subscriber",
                    normalized_term="subscriber",
                    chunk_id="cme_doc_1",
                    document_name="test.pdf",
                    document_path="test.pdf",
                    section_heading="Definitions",
                    page_start=1,
                    page_end=1,
                    definition_text="A person receiving data.",
                    provider="cme",
                )
            ]
        }

        result = format_definitions_for_output(definitions)

        assert len(result) == 1
        assert result[0]["term"] == "Subscriber"
        assert result[0]["definition"] == "A person receiving data."
        assert result[0]["document"] == "test.pdf"
        assert result[0]["provider"] == "cme"  # Now uses entry.provider directly

    def test_empty_definitions(self) -> None:
        """Returns empty list for empty definitions."""
        result = format_definitions_for_output({})
        assert result == []


class TestCommonDefinedTerms:
    """Tests for common defined terms list."""

    def test_contains_expected_terms(self) -> None:
        """Contains expected market data licensing terms."""
        assert "subscriber" in COMMON_DEFINED_TERMS
        assert "vendor" in COMMON_DEFINED_TERMS
        assert "derived data" in COMMON_DEFINED_TERMS
        assert "redistribution" in COMMON_DEFINED_TERMS
        assert "professional" in COMMON_DEFINED_TERMS

    def test_is_frozenset(self) -> None:
        """Is a frozenset for hashability and immutability."""
        assert isinstance(COMMON_DEFINED_TERMS, frozenset)
