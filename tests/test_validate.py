# tests/test_validate.py
"""Tests for LLM output validation."""

from app.validate import ValidationResult
from app.validate import get_stricter_system_prompt
from app.validate import validate_llm_output


class TestValidateAnswer:
    """Tests for validating properly formatted answers."""

    def test_valid_answer_passes(self):
        """Valid answer with all required sections should pass."""
        output = """## Answer
The fee for real-time data is $500 per month according to the CME fee schedule.

## Supporting Clauses
> "Real-time market data subscription: $500/month for professional users"
> — [CME] Market Data Fee List, Section 2.1, Page 5

## Citations
- **[CME] Market Data Fee List** (Page 5): Section 2.1 - Professional Data Fees

## Notes
- This fee applies to professional users only
"""
        result = validate_llm_output(output, ["cme"])

        assert result.is_valid
        assert not result.is_refusal
        assert len(result.errors) == 0

    def test_answer_missing_supporting_clauses(self):
        """Answer missing Supporting Clauses section should fail."""
        output = """## Answer
The fee is $500 per month.

## Citations
- **[CME] Fee List** (Page 5): Data Fees
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        assert not result.is_refusal
        assert any("Supporting Clauses" in error for error in result.errors)

    def test_answer_missing_citations(self):
        """Answer missing Citations section should fail."""
        output = """## Answer
The fee is $500 per month.

## Supporting Clauses
> "Fee: $500/month"
> — [CME] Fee List, Page 5
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        assert not result.is_refusal
        assert any("Citations" in error for error in result.errors)

    def test_answer_missing_answer_section(self):
        """Answer missing Answer section header should fail."""
        output = """The fee is $500 per month.

## Supporting Clauses
> "Fee: $500/month"
> — [CME] Fee List, Page 5

## Citations
- **[CME] Fee List** (Page 5): Data Fees
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        assert any("Answer" in error for error in result.errors)

    def test_answer_with_page_numbers_no_warnings(self):
        """Answer with proper page numbers should have no warnings."""
        output = """## Answer
The fee is $500 per month.

## Supporting Clauses
> "Fee: $500/month"
> — [CME] Fee List, Page 5

## Citations
- **[CME] Market Data Fee List** (Page 5): Section 2.1
- **[CME] Terms and Conditions** (Pages 10-12): Vendor Obligations
"""
        result = validate_llm_output(output, ["cme"])

        assert result.is_valid
        assert len(result.warnings) == 0

    def test_answer_missing_page_numbers_warns(self):
        """Answer with citations missing page numbers should warn."""
        output = """## Answer
The fee is $500 per month.

## Supporting Clauses
> "Fee: $500/month"
> — [CME] Fee List, Page 5

## Citations
- **[CME] Market Data Fee List**: Section 2.1
- **[CME] Terms and Conditions** (Pages 10-12): Vendor Obligations
"""
        result = validate_llm_output(output, ["cme"])

        assert result.is_valid  # Warnings don't make it invalid
        assert len(result.warnings) > 0
        assert any("page number" in warning.lower() for warning in result.warnings)


class TestValidateRefusal:
    """Tests for validating refusal responses."""

    def test_valid_refusal_single_source(self):
        """Valid refusal for single source should pass."""
        output = """## Answer
This is not addressed in the provided CME documents. The fee schedule does not include pricing for derivative products.

## Notes
- The available documents only cover spot market data fees
"""
        result = validate_llm_output(output, ["cme"])

        assert result.is_valid
        assert result.is_refusal
        assert len(result.errors) == 0

    def test_valid_refusal_multiple_sources(self):
        """Valid refusal for multiple sources should pass."""
        output = """## Answer
This is not addressed in the provided CME, OPRA documents. The fee schedules do not specify requirements for non-display usage.
"""
        result = validate_llm_output(output, ["cme", "opra"])

        assert result.is_valid
        assert result.is_refusal
        assert len(result.errors) == 0

    def test_refusal_with_supporting_clauses_fails(self):
        """Refusal should not include Supporting Clauses section."""
        output = """## Answer
This is not addressed in the provided CME documents.

## Supporting Clauses
> "Some quote here"
> — [CME] Document, Page 5
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        assert result.is_refusal
        assert any(
            "Supporting Clauses" in error and "omitted" in error
            for error in result.errors
        )

    def test_refusal_wrong_format_fails(self):
        """Refusal with incorrect format should fail."""
        output = """## Answer
I cannot answer this question based on the provided documents.
"""
        result = validate_llm_output(output, ["cme"])

        # This is not detected as refusal (wrong format), so it's treated as answer
        # and fails because it's missing Supporting Clauses and Citations
        assert not result.is_valid
        assert not result.is_refusal
        # Should fail validation because answer is missing required sections
        assert len(result.errors) > 0

    def test_refusal_missing_provider_name(self):
        """Refusal without provider name should fail."""
        output = """## Answer
This is not addressed in the provided documents.
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        # Should fail because it doesn't match "CME documents"

    def test_refusal_wrong_provider_name(self):
        """Refusal with wrong provider name should fail."""
        output = """## Answer
This is not addressed in the provided OPRA documents.
"""
        result = validate_llm_output(output, ["cme"])

        # Asking about CME but refusal says OPRA
        assert not result.is_valid


class TestRefusalDetection:
    """Tests for detecting whether output is refusal or answer."""

    def test_detects_refusal_single_source(self):
        """Should detect refusal for single source."""
        output = """## Answer
This is not addressed in the provided CME documents.
"""
        result = validate_llm_output(output, ["cme"])

        assert result.is_refusal

    def test_detects_refusal_multiple_sources(self):
        """Should detect refusal for multiple sources."""
        output = """## Answer
This is not addressed in the provided CME, OPRA, CTA documents.
"""
        result = validate_llm_output(output, ["cme", "opra", "cta"])

        assert result.is_refusal

    def test_detects_answer_not_refusal(self):
        """Should not detect answer as refusal."""
        output = """## Answer
The fee is $500 per month.

## Supporting Clauses
> "Fee: $500/month"
> — [CME] Fee List, Page 5

## Citations
- **[CME] Fee List** (Page 5): Section 2.1
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_refusal


class TestStricterSystemPrompt:
    """Tests for generating stricter system prompts."""

    def test_adds_warning_banner(self):
        """Stricter prompt should add validation warning banner."""
        original = "You are a legal assistant."
        stricter = get_stricter_system_prompt(original)

        assert "CRITICAL VALIDATION WARNING" in stricter
        assert "previous response failed" in stricter
        assert original in stricter

    def test_preserves_original_prompt(self):
        """Stricter prompt should preserve original content."""
        original = "You are a legal assistant specializing in market data."
        stricter = get_stricter_system_prompt(original)

        assert original in stricter

    def test_mentions_required_sections(self):
        """Stricter prompt should remind about required sections."""
        original = "You are a legal assistant."
        stricter = get_stricter_system_prompt(original)

        assert "## Answer" in stricter
        assert "## Supporting Clauses" in stricter
        assert "## Citations" in stricter

    def test_mentions_page_numbers(self):
        """Stricter prompt should remind about page numbers."""
        original = "You are a legal assistant."
        stricter = get_stricter_system_prompt(original)

        assert "page number" in stricter.lower()


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Should create ValidationResult with all fields."""
        result = ValidationResult(
            is_valid=True,
            is_refusal=False,
            errors=[],
            warnings=["Missing page number"],
        )

        assert result.is_valid
        assert not result.is_refusal
        assert len(result.errors) == 0
        assert len(result.warnings) == 1

    def test_invalid_result_with_errors(self):
        """Invalid result should have errors."""
        result = ValidationResult(
            is_valid=False,
            is_refusal=False,
            errors=["Missing Citations section"],
            warnings=[],
        )

        assert not result.is_valid
        assert len(result.errors) == 1


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_output(self):
        """Empty output should fail validation."""
        result = validate_llm_output("", ["cme"])

        assert not result.is_valid
        assert "Answer" in result.errors[0]

    def test_only_whitespace(self):
        """Whitespace-only output should fail validation."""
        result = validate_llm_output("   \n\n   ", ["cme"])

        assert not result.is_valid

    def test_malformed_sections(self):
        """Malformed section headers should fail validation."""
        output = """Answer (no ##)
The fee is $500.

Supporting Clauses (no ##)
Some text here
"""
        result = validate_llm_output(output, ["cme"])

        assert not result.is_valid
        assert any("Answer" in error for error in result.errors)

    def test_multiple_sources_validation(self):
        """Should validate refusal format with multiple sources correctly."""
        output = """## Answer
This is not addressed in the provided CME, OPRA documents.
"""
        result = validate_llm_output(output, ["cme", "opra"])

        assert result.is_valid
        assert result.is_refusal

    def test_case_sensitivity_provider_names(self):
        """Provider names should be case-insensitive in validation."""
        # Validator expects uppercase in canonical format
        output = """## Answer
This is not addressed in the provided CME documents.
"""
        result = validate_llm_output(output, ["cme"])  # lowercase input

        assert result.is_valid
        assert result.is_refusal
