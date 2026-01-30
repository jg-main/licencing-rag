# tests/test_normalize.py
"""Tests for query normalization."""

from app.normalize import extract_year_from_query
from app.normalize import normalize_query


class TestExtractYearFromQuery:
    """Tests for extract_year_from_query function."""

    def test_extract_year_2025(self) -> None:
        """Extract year 2025 from query."""
        assert extract_year_from_query("What are the 2025 fees?") == 2025

    def test_extract_year_2024(self) -> None:
        """Extract year 2024 from query."""
        assert extract_year_from_query("fee schedule for 2024") == 2024

    def test_no_year_returns_none(self) -> None:
        """Query without year returns None."""
        assert extract_year_from_query("What is the display device fee?") is None

    def test_extract_year_1990s(self) -> None:
        """Extract historical years from 1990s."""
        assert extract_year_from_query("What were the 1995 rates?") == 1995
        assert extract_year_from_query("1999 fee schedule") == 1999

    def test_extract_year_2000s(self) -> None:
        """Extract years from 2000s."""
        assert extract_year_from_query("2005 data fees") == 2005
        assert extract_year_from_query("Show 2018 schedule") == 2018

    def test_extract_year_future(self) -> None:
        """Extract future years (2030+)."""
        assert extract_year_from_query("projected 2035 fees") == 2035
        assert extract_year_from_query("2050 schedule") == 2050

    def test_extract_year_boundary_1990(self) -> None:
        """Year 1990 is the lower boundary."""
        assert extract_year_from_query("1990 data") == 1990
        # 1989 is out of range
        assert extract_year_from_query("1989 data") is None

    def test_extract_year_boundary_2099(self) -> None:
        """Year 2099 is the upper boundary."""
        assert extract_year_from_query("2099 projections") == 2099
        # 2100 is out of range
        assert extract_year_from_query("2100 projections") is None

    def test_extract_first_year_when_multiple(self) -> None:
        """When multiple years present, extract first one."""
        result = extract_year_from_query("Compare 2024 vs 2025 fees")
        assert result == 2024


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
        """Strip 'can you' leading phrase (spec v0.4)."""
        result = normalize_query("Can you explain redistribution requirements?")
        # Matches spec example exactly: 'can you' stripped, 'explain' removed (filler)
        assert result == "redistribution requirements"

    def test_strip_leading_how_does(self) -> None:
        """Strip 'how does' leading phrase (spec v0.4)."""
        result = normalize_query("How does CME charge for real-time data?")
        assert result == "cme charge real-time data"

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
        """Multiple filler words are removed (spec v0.4 filler list)."""
        result = normalize_query("What is the cost for the subscriber?")
        # 'what is' stripped, 'the' removed (filler), 'for' kept (not in spec), 'the' removed
        assert "cost" in result
        assert "subscriber" in result

    def test_preserve_numbers(self) -> None:
        """Numbers are preserved in queries."""
        result = normalize_query("What is the fee for 2024?")
        assert result == "fee 2024"

    def test_complex_query(self) -> None:
        """Complex query with multiple transformations (spec v0.4)."""
        result = normalize_query("Can you explain the professional subscriber fees?")
        # 'can you' stripped, 'explain' removed (filler), 'the' removed (filler)
        assert "professional" in result
        assert "subscriber" in result
        assert "fees" in result
        # Filler words should be removed
        assert "the" not in result
        assert "explain" not in result

    def test_empty_query(self) -> None:
        """Empty query returns empty string."""
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""

    def test_query_with_only_fillers(self) -> None:
        """Query with only filler words returns empty or minimal (spec v0.4)."""
        result = normalize_query("What is the")
        # After stripping "what is" and removing "the", should be empty
        assert result == ""

    def test_preserve_case_insensitive_domain_terms(self) -> None:
        """Domain terms are preserved regardless of case."""
        result = normalize_query("What are the FEE schedules?")
        assert "fee" in result
        assert "schedules" in result

    def test_strip_whats_prefix(self) -> None:
        """Strip "what's" leading phrase (spec v0.4)."""
        result = normalize_query("What's the fee schedule?")
        assert result == "fee schedule"

    def test_exhibit_and_table_preserved(self) -> None:
        """Legal document terms like exhibit and table are preserved (spec v0.4)."""
        result = normalize_query("What is the fee table?")
        # 'what is' stripped, 'the' removed
        assert "fee" in result
        assert "table" in result

    def test_redistribution_terms(self) -> None:
        """Redistribution and licensing terms are preserved (spec v0.4)."""
        result = normalize_query("Can you explain the redistribution rights?")
        # 'can you' stripped, 'explain' removed (filler), 'the' removed (filler)
        assert "redistribution" in result
        assert "rights" in result
        assert "explain" not in result

    def test_real_world_query_1(self) -> None:
        """Real-world example from spec v0.4: fee schedule inquiry."""
        result = normalize_query("What is the fee schedule for CME data?")
        # Exact spec example
        assert result == "fee schedule cme data"

    def test_real_world_query_2(self) -> None:
        """Real-world example from spec v0.4: redistribution."""
        result = normalize_query("Can you explain redistribution requirements?")
        # Exact spec example - 'explain' is removed as filler word
        assert result == "redistribution requirements"

    def test_real_world_query_3(self) -> None:
        """Real-world example from spec v0.4: charging."""
        result = normalize_query("How does CME charge for real-time data?")
        # Exact spec example - 'for' is not in filler words list
        assert result == "cme charge real-time data"

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
        """'How' questions are normalized correctly (spec v0.4)."""
        result = normalize_query("How does the system work?")
        # 'how does' stripped
        assert "system" in result
        assert "work" in result

    def test_would_you_prefix(self) -> None:
        """Strip 'would you' leading phrase (spec v0.4)."""
        result = normalize_query("Would you explain the terms?")
        # 'would you' stripped, 'explain' removed (filler), 'the' removed
        assert result == "terms"

    def test_could_you_prefix(self) -> None:
        """Strip 'could you' leading phrase (spec v0.4)."""
        result = normalize_query("Could you clarify the fees?")
        assert result == "clarify fees"

    def test_how_is_prefix(self) -> None:
        """Strip 'how is' leading phrase (spec v0.4)."""
        result = normalize_query("How is the fee calculated?")
        assert result == "fee calculated"

    def test_modal_verbs_removed(self) -> None:
        """Modal verbs are removed as filler words (spec v0.4)."""
        result = normalize_query("The vendor must comply with terms")
        # 'the' removed, 'must' removed (modal verb), 'with' removed
        assert "vendor" in result
        assert "comply" in result
        assert "terms" in result
        assert "must" not in result

    def test_pronouns_removed(self) -> None:
        """Pronouns are removed as filler words (spec v0.4)."""
        result = normalize_query("Can I see your fee schedule?")
        # 'can' is not a prefix by itself (only 'can you'), 'i' removed (pronoun), 'your' removed (pronoun)
        assert "see" in result
        assert "fee" in result
        assert "schedule" in result
        assert "your" not in result

    def test_whitespace_handling(self) -> None:
        """Extra whitespace is normalized."""
        # Whitespace is collapsed before prefix matching, so "What   is" matches "what is"
        result = normalize_query("  What   is    the   fee?  ")
        assert result == "fee"
        # No extra consecutive spaces in output
        assert "  " not in result
