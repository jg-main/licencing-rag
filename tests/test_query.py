# tests/test_query.py
"""Tests for query pipeline."""

import pytest

from app.prompts import QA_PROMPT, SYSTEM_PROMPT, get_refusal_message


class TestPrompts:
    """Tests for prompt templates."""

    def test_system_prompt_has_required_sections(self) -> None:
        """System prompt includes required output format."""
        assert "## Answer" in SYSTEM_PROMPT
        assert "## Supporting Clauses" in SYSTEM_PROMPT
        assert "## Citations" in SYSTEM_PROMPT
        assert "## Notes" in SYSTEM_PROMPT

    def test_system_prompt_requires_provider_in_citations(self) -> None:
        """System prompt requires provider prefix in citations."""
        assert "[PROVIDER]" in SYSTEM_PROMPT

    def test_system_prompt_requires_page_ranges(self) -> None:
        """System prompt mentions page ranges."""
        assert "Pages" in SYSTEM_PROMPT

    def test_qa_prompt_has_placeholders(self) -> None:
        """QA prompt has required placeholders."""
        assert "{provider}" in QA_PROMPT
        assert "{context}" in QA_PROMPT
        assert "{question}" in QA_PROMPT


class TestRefusalMessage:
    """Tests for refusal message generation."""

    def test_single_provider_refusal(self) -> None:
        """Single provider refusal message."""
        msg = get_refusal_message(["cme"])
        assert "CME" in msg
        assert "not addressed" in msg.lower()

    def test_multiple_provider_refusal(self) -> None:
        """Multiple provider refusal message."""
        msg = get_refusal_message(["cme", "ice"])
        assert "CME" in msg
        assert "ICE" in msg

    def test_empty_provider_refusal(self) -> None:
        """Empty provider list doesn't crash."""
        msg = get_refusal_message([])
        assert isinstance(msg, str)
