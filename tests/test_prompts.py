# tests/test_prompts.py
"""Tests for LLM prompts (Phase 7) - Prompt Discipline validation.

These tests verify that prompts enforce accuracy requirements and
maintain consistent refusal behavior.
"""

from app.prompts import QA_PROMPT
from app.prompts import QA_PROMPT_NO_DEFINITIONS
from app.prompts import SYSTEM_PROMPT
from app.prompts import get_refusal_message


class TestSystemPrompt:
    """Test SYSTEM_PROMPT structure and requirements."""

    def test_system_prompt_contains_strict_rules(self):
        """System prompt must include strict accuracy rules."""
        assert "STRICT RULES" in SYSTEM_PROMPT
        assert "NEVER" in SYSTEM_PROMPT
        assert "ONLY using the provided context" in SYSTEM_PROMPT

    def test_system_prompt_emphasizes_no_external_knowledge(self):
        """System prompt must explicitly forbid external knowledge."""
        assert "external knowledge" in SYSTEM_PROMPT.lower()
        assert "training data" in SYSTEM_PROMPT.lower()
        assert "assumptions" in SYSTEM_PROMPT.lower()

    def test_system_prompt_requires_citations(self):
        """System prompt must require citations."""
        assert "citation" in SYSTEM_PROMPT.lower() or "cite" in SYSTEM_PROMPT.lower()
        assert "PROVIDER" in SYSTEM_PROMPT
        assert "Document Name" in SYSTEM_PROMPT
        assert "Page" in SYSTEM_PROMPT

    def test_system_prompt_includes_refusal_instruction(self):
        """System prompt must include explicit refusal instructions."""
        assert "refuse" in SYSTEM_PROMPT.lower() or "refusal" in SYSTEM_PROMPT.lower()
        assert "not addressed" in SYSTEM_PROMPT.lower()

    def test_system_prompt_forbids_inference(self):
        """System prompt must explicitly forbid inference and extrapolation."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "infer" in prompt_lower or "inference" in prompt_lower
        assert "extrapolate" in prompt_lower

    def test_system_prompt_requires_exact_quotes(self):
        """System prompt must encourage exact quotes over paraphrasing."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "quote" in prompt_lower or "quoted" in prompt_lower
        assert "verbatim" in prompt_lower or "exact" in prompt_lower

    def test_system_prompt_includes_output_format(self):
        """System prompt must specify required output format."""
        assert "## Answer" in SYSTEM_PROMPT
        assert "## Supporting Clauses" in SYSTEM_PROMPT
        assert "## Definitions" in SYSTEM_PROMPT
        assert "## Citations" in SYSTEM_PROMPT

    def test_system_prompt_emphasizes_accuracy_over_cost(self):
        """System prompt must prioritize accuracy over other concerns."""
        prompt_lower = SYSTEM_PROMPT.lower()
        # Check for accuracy-first language
        assert (
            "accuracy" in prompt_lower
            or "accurate" in prompt_lower
            or "mandatory" in prompt_lower
        )

    def test_system_prompt_includes_verification_steps(self):
        """System prompt must include pre-response verification."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "verification" in prompt_lower or "verify" in prompt_lower
        assert "before" in prompt_lower

    def test_system_prompt_forbids_partial_answers(self):
        """System prompt must forbid partial answers with assumptions."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "partial" in prompt_lower
        # Should forbid mixing context with assumptions
        forbidden_patterns = ["do not", "never", "must not"]
        assert any(pattern in prompt_lower for pattern in forbidden_patterns)

    def test_system_prompt_includes_forbidden_patterns(self):
        """System prompt should list forbidden response patterns."""
        prompt_lower = SYSTEM_PROMPT.lower()
        # Check for examples of what NOT to do
        assert "forbidden" in prompt_lower or "❌" in SYSTEM_PROMPT

    def test_system_prompt_formatted_for_readability(self):
        """System prompt should use clear formatting for LLM parsing."""
        # Check for section separators or clear structure
        assert "═══" in SYSTEM_PROMPT or "---" in SYSTEM_PROMPT or "##" in SYSTEM_PROMPT


class TestQAPrompts:
    """Test QA prompt templates."""

    def test_qa_prompt_includes_context_placeholder(self):
        """QA prompt must include context placeholder."""
        assert "{context}" in QA_PROMPT
        assert "{context}" in QA_PROMPT_NO_DEFINITIONS

    def test_qa_prompt_includes_question_placeholder(self):
        """QA prompt must include question placeholder."""
        assert "{question}" in QA_PROMPT
        assert "{question}" in QA_PROMPT_NO_DEFINITIONS

    def test_qa_prompt_includes_provider_placeholder(self):
        """QA prompt must include provider placeholder."""
        assert "{source}" in QA_PROMPT
        assert "{source}" in QA_PROMPT_NO_DEFINITIONS

    def test_qa_prompt_with_definitions_has_placeholder(self):
        """QA prompt with definitions must have definitions placeholder."""
        assert "{definitions_section}" in QA_PROMPT

    def test_qa_prompt_without_definitions_has_no_placeholder(self):
        """QA prompt without definitions must not have definitions placeholder."""
        assert "{definitions_section}" not in QA_PROMPT_NO_DEFINITIONS

    def test_qa_prompt_reinforces_grounding_requirement(self):
        """QA prompt must reinforce grounding in context."""
        assert "ONLY" in QA_PROMPT or "only" in QA_PROMPT
        assert "context" in QA_PROMPT.lower()

    def test_qa_prompt_includes_refusal_format(self):
        """QA prompt must specify refusal format."""
        assert "not addressed" in QA_PROMPT.lower()
        assert "not addressed" in QA_PROMPT_NO_DEFINITIONS.lower()

    def test_qa_prompt_includes_verification_checklist(self):
        """QA prompt should include pre-response verification."""
        prompt_lower = QA_PROMPT.lower()
        assert "verification" in prompt_lower or "verify" in prompt_lower

    def test_qa_prompt_includes_refusal_criteria(self):
        """QA prompt should list refusal criteria."""
        prompt_lower = QA_PROMPT.lower()
        assert "refuse" in prompt_lower or "refusal" in prompt_lower

    def test_qa_prompt_emphasizes_accuracy_over_helpfulness(self):
        """QA prompt must prioritize accuracy over user satisfaction."""
        prompt_lower = QA_PROMPT.lower()
        assert "accuracy" in prompt_lower or "accurate" in prompt_lower


class TestRefusalMessage:
    """Test refusal message generation."""

    def test_refusal_message_single_provider(self):
        """Refusal message should be specific to single provider."""
        msg = get_refusal_message(["cme"])
        assert "CME" in msg
        assert "not addressed" in msg.lower()

    def test_refusal_message_multiple_providers(self):
        """Refusal message should list multiple providers."""
        msg = get_refusal_message(["cme", "opra"])
        assert "CME" in msg
        assert "OPRA" in msg
        assert "not addressed" in msg.lower()

    def test_refusal_message_uppercase_providers(self):
        """Refusal message should uppercase provider names."""
        msg = get_refusal_message(["cme"])
        assert "CME" in msg
        assert "cme" not in msg  # Should be uppercase

    def test_refusal_message_consistency(self):
        """Refusal messages should be consistent."""
        msg1 = get_refusal_message(["cme"])
        msg2 = get_refusal_message(["cme"])
        assert msg1 == msg2


class TestPromptIntegration:
    """Integration tests for prompt behavior."""

    def test_system_and_qa_prompts_are_compatible(self):
        """System prompt and QA prompt should work together."""
        # Both should reference the same output format
        assert "## Answer" in SYSTEM_PROMPT
        # QA prompt should reinforce system prompt requirements
        assert "ONLY" in QA_PROMPT or "only" in QA_PROMPT

    def test_prompts_support_definitions_workflow(self):
        """Prompts should support optional definitions."""
        # System prompt mentions definitions
        assert "Definition" in SYSTEM_PROMPT or "definition" in SYSTEM_PROMPT.lower()
        # QA prompt has variant for with/without definitions
        assert "{definitions_section}" in QA_PROMPT
        assert "{definitions_section}" not in QA_PROMPT_NO_DEFINITIONS

    def test_prompts_enforce_citation_format(self):
        """Prompts should specify citation format."""
        # System prompt should show citation format
        assert "[PROVIDER]" in SYSTEM_PROMPT
        # Should specify page format
        assert "Page" in SYSTEM_PROMPT


class TestPromptAccuracyRequirements:
    """Test that prompts enforce accuracy-first requirements."""

    def test_prompt_forbids_general_knowledge(self):
        """Prompts must explicitly forbid general knowledge."""
        combined = SYSTEM_PROMPT + QA_PROMPT
        assert "general knowledge" in combined.lower()
        assert "external knowledge" in combined.lower()

    def test_prompt_forbids_typical_practice(self):
        """Prompts should forbid 'typical practice' answers."""
        prompt_lower = SYSTEM_PROMPT.lower()
        # Should either forbid it explicitly or set strict grounding requirements
        assert "typical" in prompt_lower or "never" in prompt_lower

    def test_prompt_requires_complete_answers(self):
        """Prompts should require complete answers or refusal."""
        combined_lower = (SYSTEM_PROMPT + QA_PROMPT).lower()
        assert "complete" in combined_lower or "partial" in combined_lower

    def test_prompt_forbids_paraphrasing_definitions(self):
        """Prompts should require exact definition quotes."""
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "exact" in prompt_lower or "verbatim" in prompt_lower

    def test_prompt_includes_quality_checklist(self):
        """Prompts should include quality verification checklist."""
        combined = SYSTEM_PROMPT + QA_PROMPT
        # Should have numbered verification steps or checklist
        assert "1." in combined or "verification" in combined.lower()


class TestPromptFormatEnforcement:
    """Test that prompts enforce output format."""

    def test_prompt_requires_answer_section(self):
        """Prompts must require Answer section."""
        assert "## Answer" in SYSTEM_PROMPT

    def test_prompt_requires_supporting_clauses_section(self):
        """Prompts must require Supporting Clauses section."""
        assert "## Supporting Clauses" in SYSTEM_PROMPT

    def test_prompt_requires_citations_section(self):
        """Prompts must require Citations section."""
        assert "## Citations" in SYSTEM_PROMPT

    def test_prompt_specifies_quote_format(self):
        """Prompts should specify how to format quotes."""
        # Should show quote formatting with > or similar
        assert ">" in SYSTEM_PROMPT or "quote" in SYSTEM_PROMPT.lower()

    def test_prompt_specifies_citation_format(self):
        """Prompts should specify citation format."""
        # Should show [PROVIDER] format
        assert "[PROVIDER]" in SYSTEM_PROMPT

    def test_prompt_allows_optional_notes_section(self):
        """Prompts should allow optional Notes section."""
        assert "## Notes" in SYSTEM_PROMPT
        # Should indicate it's optional
        assert "OPTIONAL" in SYSTEM_PROMPT or "omit" in SYSTEM_PROMPT.lower()
