# tests/test_output.py
"""Tests for output formatters."""

import json
from unittest.mock import patch

import pytest

from app.output import OutputFormat
from app.output import QueryResult
from app.output import _extract_clauses
from app.output import format_console
from app.output import format_json
from app.output import print_result


@pytest.fixture
def sample_result() -> dict:
    """Create a sample query result for testing."""
    return {
        "answer": "The **subscriber fee** is $100 per month.\n\nSee Section 3.1.",
        "context": (
            "--- [CME] Fees/Schedule-A.pdf | Section 3.1 Pricing | Page 5 ---\n"
            "Subscriber fees are $100 per month for professional users.\n\n"
            "--- [CME] Agreements/Main-Agreement.pdf | Section 2.0 Definitions | "
            "Pages 2-3 ---\n"
            '"Subscriber" means any individual authorized to receive market data.'
        ),
        "citations": [
            {
                "provider": "cme",
                "document": "Fees/Schedule-A.pdf",
                "section": "Section 3.1 Pricing",
                "page_start": 5,
                "page_end": 5,
            },
            {
                "provider": "cme",
                "document": "Agreements/Main-Agreement.pdf",
                "section": "Section 2.0 Definitions",
                "page_start": 2,
                "page_end": 3,
            },
        ],
        "definitions": [
            {
                "term": "Subscriber",
                "definition": (
                    '"Subscriber" means any individual authorized to receive market '
                    "data from a Vendor under a valid subscription agreement."
                ),
                "document_path": "Agreements/Main-Agreement.pdf",
                "section": "Section 2.0 Definitions",
                "page_start": 2,
                "page_end": 2,
                "provider": "cme",
            },
        ],
        "chunks_retrieved": 2,
        "providers": ["cme"],
        "search_mode": "hybrid",
        "effective_search_mode": "hybrid",
    }


@pytest.fixture
def minimal_result() -> dict:
    """Create a minimal query result with no citations or definitions."""
    return {
        "answer": "This is not addressed in the provided documents.",
        "context": "",
        "citations": [],
        "definitions": [],
        "chunks_retrieved": 0,
        "providers": ["cme"],
        "search_mode": "vector",
        "effective_search_mode": "vector",
    }


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_from_dict_full(self, sample_result: dict) -> None:
        """Test creating QueryResult from a full result dictionary."""
        qr = QueryResult.from_dict(sample_result)

        assert qr.answer == sample_result["answer"]
        assert qr.context == sample_result["context"]
        assert len(qr.citations) == 2
        assert len(qr.definitions) == 1
        assert qr.chunks_retrieved == 2
        assert qr.providers == ["cme"]
        assert qr.search_mode == "hybrid"
        assert qr.effective_search_mode == "hybrid"

    def test_from_dict_minimal(self, minimal_result: dict) -> None:
        """Test creating QueryResult from a minimal result dictionary."""
        qr = QueryResult.from_dict(minimal_result)

        assert qr.answer == minimal_result["answer"]
        assert qr.context == ""
        assert qr.citations == []
        assert qr.definitions == []
        assert qr.chunks_retrieved == 0

    def test_from_dict_missing_fields(self) -> None:
        """Test creating QueryResult from dict with missing fields."""
        qr = QueryResult.from_dict({})

        assert qr.answer == ""
        assert qr.context == ""
        assert qr.citations == []
        assert qr.definitions == []
        assert qr.chunks_retrieved == 0
        assert qr.providers == []
        assert qr.search_mode == ""
        assert qr.effective_search_mode == ""


class TestFormatConsole:
    """Tests for console output formatter."""

    def test_format_console_returns_string(self, sample_result: dict) -> None:
        """Test that format_console returns a non-empty string."""
        output = format_console(sample_result)

        assert isinstance(output, str)
        assert len(output) > 0

    def test_format_console_contains_answer(self, sample_result: dict) -> None:
        """Test that console output contains the answer."""
        output = format_console(sample_result)

        # The answer text should appear (markdown may be stripped)
        assert "subscriber fee" in output.lower() or "100" in output

    def test_format_console_contains_provider(self, sample_result: dict) -> None:
        """Test that console output contains provider info."""
        output = format_console(sample_result)

        assert "CME" in output

    def test_format_console_contains_citations(self, sample_result: dict) -> None:
        """Test that console output contains citation documents."""
        output = format_console(sample_result)

        assert "Schedule-A" in output or "Fees" in output

    def test_format_console_contains_definitions(self, sample_result: dict) -> None:
        """Test that console output contains definitions."""
        output = format_console(sample_result)

        assert "Subscriber" in output

    def test_format_console_minimal_result(self, minimal_result: dict) -> None:
        """Test console formatting with minimal result."""
        output = format_console(minimal_result)

        assert isinstance(output, str)
        assert "not addressed" in output.lower() or "0 chunks" in output

    def test_format_console_multiple_providers(self) -> None:
        """Test console formatting with multiple providers."""
        result = {
            "answer": "Test answer",
            "context": "",
            "citations": [],
            "definitions": [],
            "chunks_retrieved": 0,
            "providers": ["cme", "opra"],
            "search_mode": "hybrid",
            "effective_search_mode": "hybrid",
        }
        output = format_console(result)

        assert "CME" in output
        assert "OPRA" in output

    def test_format_console_search_mode_fallback(self) -> None:
        """Test console shows fallback when effective mode differs."""
        result = {
            "answer": "Test answer",
            "context": "",
            "citations": [],
            "definitions": [],
            "chunks_retrieved": 0,
            "providers": ["cme"],
            "search_mode": "hybrid",
            "effective_search_mode": "vector",
        }
        output = format_console(result)

        # Should indicate fallback occurred
        assert "fell back" in output.lower() or "fallback" in output.lower()


class TestFormatJson:
    """Tests for JSON output formatter."""

    def test_format_json_returns_valid_json(self, sample_result: dict) -> None:
        """Test that format_json returns valid JSON."""
        output = format_json(sample_result)

        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_json_schema(self, sample_result: dict) -> None:
        """Test that JSON output has the expected schema."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        # Check top-level keys
        assert "answer" in parsed
        assert "supporting_clauses" in parsed
        assert "definitions" in parsed
        assert "citations" in parsed
        assert "metadata" in parsed

    def test_format_json_answer(self, sample_result: dict) -> None:
        """Test that JSON contains the answer."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        assert parsed["answer"] == sample_result["answer"]

    def test_format_json_citations(self, sample_result: dict) -> None:
        """Test that JSON contains structured citations."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        citations = parsed["citations"]
        assert len(citations) == 2

        # Check citation structure
        cit = citations[0]
        assert "provider" in cit
        assert "document" in cit
        assert "section" in cit
        assert "page_start" in cit
        assert "page_end" in cit

    def test_format_json_definitions(self, sample_result: dict) -> None:
        """Test that JSON contains structured definitions."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        definitions = parsed["definitions"]
        assert len(definitions) == 1

        # Check definition structure
        defn = definitions[0]
        assert defn["term"] == "Subscriber"
        assert "definition" in defn
        assert "source" in defn
        assert "provider" in defn["source"]
        assert "document" in defn["source"]

    def test_format_json_metadata(self, sample_result: dict) -> None:
        """Test that JSON contains metadata."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        metadata = parsed["metadata"]
        assert metadata["providers"] == ["cme"]
        assert metadata["chunks_retrieved"] == 2
        assert metadata["search_mode"] == "hybrid"
        assert metadata["effective_search_mode"] == "hybrid"
        assert "timestamp" in metadata

    def test_format_json_timestamp_format(self, sample_result: dict) -> None:
        """Test that timestamp is ISO-8601 format."""
        output = format_json(sample_result)
        parsed = json.loads(output)

        timestamp = parsed["metadata"]["timestamp"]
        # Should contain T and timezone info
        assert "T" in timestamp
        assert "+" in timestamp or "Z" in timestamp

    def test_format_json_compact(self, sample_result: dict) -> None:
        """Test compact JSON output (pretty=False)."""
        output = format_json(sample_result, pretty=False)

        # Should not have indentation
        assert "\n  " not in output

        # Should still be valid JSON
        parsed = json.loads(output)
        assert "answer" in parsed

    def test_format_json_minimal_result(self, minimal_result: dict) -> None:
        """Test JSON formatting with minimal result."""
        output = format_json(minimal_result)
        parsed = json.loads(output)

        assert parsed["answer"] == minimal_result["answer"]
        assert parsed["supporting_clauses"] == []
        assert parsed["definitions"] == []
        assert parsed["citations"] == []
        assert parsed["metadata"]["chunks_retrieved"] == 0


class TestExtractClauses:
    """Tests for _extract_clauses helper function."""

    def test_extract_clauses_from_context(self) -> None:
        """Test extracting clauses from formatted context."""
        context = (
            "--- [CME] Document.pdf | Section 1 | Page 5 ---\n"
            "First clause text here.\n\n"
            "--- [CME] Another.pdf | Section 2 | Pages 10-12 ---\n"
            "Second clause text here."
        )

        clauses = _extract_clauses(context)

        assert len(clauses) == 2
        assert clauses[0]["text"] == "First clause text here."
        assert clauses[0]["source"]["provider"] == "CME"
        assert clauses[0]["source"]["document"] == "Document.pdf"
        assert clauses[0]["source"]["page_start"] == 5

    def test_extract_clauses_page_range(self) -> None:
        """Test extracting clauses with page ranges."""
        context = "--- [CME] Document.pdf | Section 1 | Pages 10-12 ---\nClause text."

        clauses = _extract_clauses(context)

        assert len(clauses) == 1
        assert clauses[0]["source"]["page_start"] == 10
        assert clauses[0]["source"]["page_end"] == 12

    def test_extract_clauses_empty_context(self) -> None:
        """Test extracting clauses from empty context."""
        clauses = _extract_clauses("")

        assert clauses == []

    def test_extract_clauses_no_headers(self) -> None:
        """Test extracting clauses from context without headers."""
        context = "Just some text without any headers."

        clauses = _extract_clauses(context)

        assert clauses == []


class TestPrintResult:
    """Tests for print_result function."""

    def test_print_result_console(self, sample_result: dict, capsys) -> None:
        """Test print_result with console format."""
        print_result(sample_result, OutputFormat.CONSOLE)

        captured = capsys.readouterr()
        # Should output to stdout
        assert len(captured.out) > 0

    def test_print_result_json(self, sample_result: dict, capsys) -> None:
        """Test print_result with JSON format."""
        print_result(sample_result, OutputFormat.JSON)

        captured = capsys.readouterr()
        # Should be valid JSON
        parsed = json.loads(captured.out)
        assert "answer" in parsed


class TestOutputFormatEnum:
    """Tests for OutputFormat enum."""

    def test_output_format_values(self) -> None:
        """Test OutputFormat enum values."""
        assert OutputFormat.CONSOLE.value == "console"
        assert OutputFormat.JSON.value == "json"

    def test_output_format_from_string(self) -> None:
        """Test creating OutputFormat from string."""
        assert OutputFormat("console") == OutputFormat.CONSOLE
        assert OutputFormat("json") == OutputFormat.JSON

    def test_output_format_invalid(self) -> None:
        """Test invalid OutputFormat raises ValueError."""
        with pytest.raises(ValueError):
            OutputFormat("invalid")
