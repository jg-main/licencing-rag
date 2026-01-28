# tests/test_normalize.py
"""Tests for query normalization."""

from app.normalize import normalize_query


class TestQueryNormalization:
    """Tests for normalize_query function."""

    def test_basic_normalization(self) -> None:
        """Basic query normalization removes filler words."""
        result = normalize_query("the fee schedule")
        assert result == "fee schedule"

    def test_strip_leading_what_is(self) -> None:
        """Strip 'what is' leading phrase."""
        result = normalize_query("What is the fee schedule?")
        assert result == "fee schedule"

    def test_strip_leading_can_you(self) -> None:
        """Strip 'can you' leading phrase."""
        result = normalize_query("Can you tell me about real-time data fees?")
        assert result == "real-time data fees"

    def test_strip_leading_where_can_i_find(self) -> None:
        """Strip 'where can i find' leading phrase."""
        result = normalize_query("Where can I find the CME exhibit?")
        assert result == "cme exhibit"

    def test_preserve_domain_terms(self) -> None:
        """Domain-specific terms are preserved."""
        result = normalize_query("What are the subscriber fees?")
        assert result == "subscriber fees"

    def test_preserve_hyphenated_terms(self) -> None:
        """Hyphenated terms like 'real-time' are preserved."""
        result = normalize_query("What is the real-time data fee?")
        assert result == "real-time data fee"

    def test_preserve_non_professional(self) -> None:
        """Hyphenated term 'non-professional' is preserved."""
        result = normalize_query("non-professional subscriber rates")
        assert result == "non-professional subscriber rates"

    def test_remove_multiple_fillers(self) -> None:
        """Multiple filler words are removed."""
        result = normalize_query("What is the cost of the data in the agreement?")
        assert result == "cost data agreement"

    def test_preserve_numbers(self) -> None:
        """Numbers are preserved in queries."""
        result = normalize_query("What is the fee for 2024?")
        assert result == "fee 2024"

    def test_complex_query(self) -> None:
        """Complex query with multiple transformations."""
        result = normalize_query(
            "Can you tell me about the professional subscriber fees in Exhibit A?"
        )
        # Should strip "Can you tell me about", remove "the", "in", preserve key terms
        assert "professional" in result
        assert "subscriber" in result
        assert "fees" in result
        assert "exhibit" in result
        # Filler words should be removed
        assert "the" not in result
        assert "in" not in result

    def test_empty_query(self) -> None:
        """Empty query returns empty string."""
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""

    def test_query_with_only_fillers(self) -> None:
        """Query with only filler words returns empty or minimal."""
        result = normalize_query("What is the")
        # After stripping "what is" and "the", should be empty
        assert result == ""

    def test_preserve_case_insensitive_domain_terms(self) -> None:
        """Domain terms are preserved regardless of case."""
        result = normalize_query("What are the FEE schedules?")
        assert "fee" in result
        assert "schedules" in result

    def test_multiple_leading_phrases(self) -> None:
        """Only the first leading phrase is stripped."""
        result = normalize_query("Tell me what is the fee?")
        # "Tell me" should be stripped, "what" preserved as a content word, "is the" removed
        assert "what" in result
        assert "fee" in result

    def test_exhibit_and_table_preserved(self) -> None:
        """Legal document terms like exhibit and table are preserved."""
        result = normalize_query("Where is the fee table in Exhibit B?")
        assert "fee" in result
        assert "table" in result
        assert "exhibit" in result

    def test_redistribution_terms(self) -> None:
        """Redistribution and licensing terms are preserved."""
        result = normalize_query("What are the redistribution rights for vendors?")
        assert "redistribution" in result
        assert "rights" in result
        assert "vendors" in result

    def test_real_world_query_1(self) -> None:
        """Real-world example: fee schedule inquiry."""
        result = normalize_query("What is the monthly fee for real-time quotes?")
        assert "monthly" in result
        assert "fee" in result
        assert "real-time" in result
        assert "quotes" in result

    def test_real_world_query_2(self) -> None:
        """Real-world example: vendor terms."""
        result = normalize_query("Can you explain the vendor redistribution fees?")
        assert "vendor" in result
        assert "redistribution" in result
        assert "fees" in result
        # Should not contain conversational words
        assert "explain" not in result

    def test_real_world_query_3(self) -> None:
        """Real-world example: subscriber classification."""
        result = normalize_query(
            "What is the difference between professional and non-professional subscribers?"
        )
        assert "professional" in result
        assert "non-professional" in result
        assert "subscribers" in result
        # "difference between" should be removed
        assert "difference" not in result or "between" not in result

    def test_punctuation_removal(self) -> None:
        """Punctuation is removed except hyphens."""
        result = normalize_query("What's the fee, schedule?")
        assert "fee" in result
        assert "schedule" in result
        # No punctuation should remain
        assert "," not in result
        assert "?" not in result

    def test_normalization_is_idempotent(self) -> None:
        """Normalizing twice produces the same result."""
        query = "What is the fee schedule?"
        normalized_once = normalize_query(query)
        normalized_twice = normalize_query(normalized_once)
        assert normalized_once == normalized_twice

    def test_how_questions(self) -> None:
        """'How' questions are normalized correctly."""
        result = normalize_query("How do I access real-time data?")
        assert "access" in result
        assert "real-time" in result
        assert "data" in result
        # "How do I" should be stripped
        assert "how" not in result

    def test_whitespace_handling(self) -> None:
        """Extra whitespace is normalized."""
        result = normalize_query("  What   is    the   fee?  ")
        assert result == "fee"
        # No extra spaces
        assert "  " not in result
