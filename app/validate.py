# app/validate.py
"""LLM output validation for compliance with required format.

This module provides code-based validation of LLM responses to ensure:
- Required sections are present
- Refusal format matches canonical template
- Citations include page numbers
- Supporting clauses are omitted when refusing

This moves some compliance guarantees from prompt text into code enforcement.
"""

import re
from dataclasses import dataclass

from app.logging import get_logger
from app.prompts import REFUSAL_TEMPLATE
from app.prompts import REQUIRED_ANSWER_SECTIONS
from app.prompts import REQUIRED_REFUSAL_SECTIONS

log = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of LLM output validation.

    Attributes:
        is_valid: Whether the output passes all validation checks.
        is_refusal: Whether the output is a refusal (not an answer).
        errors: List of validation error messages.
        warnings: List of non-critical validation warnings.
    """

    is_valid: bool
    is_refusal: bool
    errors: list[str]
    warnings: list[str]


def validate_llm_output(output: str, sources: list[str]) -> ValidationResult:
    """Validate LLM output for compliance with required format.

    Args:
        output: The raw LLM response text.
        sources: List of source names (e.g., ["cme", "opra"]) for refusal validation.

    Returns:
        ValidationResult with validation status and any errors/warnings.
    """
    errors = []
    warnings = []
    is_refusal = _is_refusal_response(output, sources)

    # Check for required sections
    section_errors = _validate_required_sections(output, is_refusal)
    errors.extend(section_errors)

    # Validate refusal format if it's a refusal
    if is_refusal:
        refusal_errors = _validate_refusal_format(output, sources)
        errors.extend(refusal_errors)

        # Check that Supporting Clauses is NOT present when refusing
        if "## Supporting Clauses" in output:
            errors.append(
                "Supporting Clauses section should be omitted when refusing to answer"
            )
    else:
        # For answers, validate citations
        citation_warnings = _validate_citations(output)
        warnings.extend(citation_warnings)

    is_valid = len(errors) == 0

    if not is_valid:
        log.warning(
            "llm_output_validation_failed",
            is_refusal=is_refusal,
            error_count=len(errors),
            errors=errors,
        )
    elif warnings:
        log.info(
            "llm_output_validation_warnings",
            is_refusal=is_refusal,
            warning_count=len(warnings),
            warnings=warnings,
        )

    return ValidationResult(
        is_valid=is_valid,
        is_refusal=is_refusal,
        errors=errors,
        warnings=warnings,
    )


def _is_refusal_response(output: str, sources: list[str]) -> bool:
    """Check if the output is a refusal rather than an answer.

    Uses REFUSAL_TEMPLATE from prompts.py for consistency.

    Args:
        output: The LLM response text.
        sources: List of source names for matching refusal pattern.

    Returns:
        True if output appears to be a refusal, False otherwise.
    """
    # Build canonical refusal using centralized template
    if len(sources) == 1:
        source_label = sources[0].upper()
    else:
        source_label = ", ".join(s.upper() for s in sources)

    canonical_refusal = REFUSAL_TEMPLATE.format(source=source_label)
    return canonical_refusal in output


def _validate_required_sections(output: str, is_refusal: bool) -> list[str]:
    """Validate that required sections are present.

    Uses REQUIRED_ANSWER_SECTIONS and REQUIRED_REFUSAL_SECTIONS from prompts.py.

    Args:
        output: The LLM response text.
        is_refusal: Whether the output is a refusal.

    Returns:
        List of error messages for missing required sections.
    """
    errors = []
    required = REQUIRED_REFUSAL_SECTIONS if is_refusal else REQUIRED_ANSWER_SECTIONS

    for section in required:
        if section not in output:
            section_type = "refusal" if is_refusal else "answer"
            errors.append(f"Missing required '{section}' section for {section_type}")

    return errors


def _validate_refusal_format(output: str, sources: list[str]) -> list[str]:
    """Validate that refusal follows canonical format.

    Uses REFUSAL_TEMPLATE from prompts.py for consistency.

    Args:
        output: The LLM response text.
        sources: List of source names for matching refusal pattern.

    Returns:
        List of error messages for refusal format violations.
    """
    errors = []

    # Build expected refusal message using centralized template
    if len(sources) == 1:
        source_label = sources[0].upper()
    else:
        source_label = ", ".join(s.upper() for s in sources)

    expected_refusal = REFUSAL_TEMPLATE.format(source=source_label)

    # Check if refusal message appears in Answer section
    if expected_refusal not in output:
        errors.append(
            f"Refusal format does not match canonical template. "
            f"Expected: '{expected_refusal}'"
        )

    return errors


def _validate_citations(output: str) -> list[str]:
    """Validate that citations include page numbers.

    Args:
        output: The LLM response text.

    Returns:
        List of warning messages for citation issues (non-critical).
    """
    warnings: list[str] = []

    # Extract Citations section
    citations_match = re.search(r"## Citations\s*\n(.*?)(?=\n##|\Z)", output, re.DOTALL)

    if not citations_match:
        # Already caught by required sections check
        return warnings

    citations_text = citations_match.group(1)

    # Look for citation patterns without page numbers
    # Expected format: "... Page X" or "Pages X-Y" or "(Page X)" or "(Pages X-Y)"
    citation_lines = [
        line.strip()
        for line in citations_text.split("\n")
        if line.strip() and line.strip().startswith("-")
    ]

    for line in citation_lines:
        # Check if line contains "Page" or "Pages"
        if "Page" not in line and "page" not in line:
            warnings.append(f"Citation may be missing page number: {line[:80]}...")

    return warnings


def get_stricter_system_prompt(original_prompt: str, sources: list[str]) -> str:
    """Generate a stricter system prompt for retry after validation failure.

    Args:
        original_prompt: The original system prompt.
        sources: List of source names for refusal format example.

    Returns:
        Enhanced system prompt with stronger validation warnings.
    """
    # Build source label for refusal example
    if len(sources) == 1:
        source_label = sources[0].upper()
    else:
        source_label = ", ".join(s.upper() for s in sources)

    refusal_example = REFUSAL_TEMPLATE.format(source=source_label)

    # Add a warning banner at the start
    warning = f"""
⚠️  CRITICAL VALIDATION WARNING ⚠️
Your previous response failed format validation. You MUST follow the output format EXACTLY.
- Include ALL required sections: ## Answer, ## Supporting Clauses, ## Citations
- Use EXACT refusal format if refusing: "{refusal_example}"
- Include page numbers in ALL citations
- Skip Supporting Clauses section ONLY when refusing

════════════════════════════════════════════════════════════════════
"""
    return warning + original_prompt
