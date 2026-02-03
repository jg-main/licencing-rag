# api/formatters/slack.py
"""Slack Block Kit formatters for RAG responses.

Formats query results into Slack's Block Kit format for rich interactive messages.
Reference: https://api.slack.com/block-kit
"""

from typing import Any


def format_answer_blocks(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Format RAG response into Slack Block Kit blocks.

    Creates a rich message with:
    - Answer section with markdown formatting
    - Citations context block
    - Definitions section (if included)
    - Footer with query metadata

    Args:
        response: Response dict from app.query.query() containing:
            - answer: The answer text
            - citations: List of citation dicts
            - definitions: List of definition dicts (optional)
            - refused: Boolean indicating if query was refused
            - refusal_reason: Reason for refusal (if refused)
            - metadata: Dict with tokens, latency, etc.

    Returns:
        List of Block Kit block objects ready for Slack API.

    Example:
        >>> blocks = format_answer_blocks({
        ...     "answer": "The fee is $100.",
        ...     "citations": [{"source": "cme", "document": "fees.pdf", "page": 1}],
        ...     "refused": False,
        ...     "metadata": {"tokens": 150, "latency_ms": 1200}
        ... })
    """
    blocks: list[dict[str, Any]] = []

    # Check if query was refused
    refused = response.get("refused", False)
    if refused:
        # Format refusal message
        refusal_reason = response.get("refusal_reason", "Unknown reason")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Unable to Answer*\n\n{refusal_reason}",
                },
            }
        )
        return blocks

    # Main answer section
    answer = response.get("answer", "")
    if answer:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Answer:*\n\n{answer}",
                },
            }
        )

    # Citations section
    citations = response.get("citations", [])
    if citations:
        # Build citation text
        citation_lines = []
        for i, cite in enumerate(citations, 1):
            source = cite.get("source", "unknown")
            document = cite.get("document", "unknown")
            page = cite.get("page")

            if page:
                citation_lines.append(f"{i}. {source}/{document} (page {page})")
            else:
                citation_lines.append(f"{i}. {source}/{document}")

        citation_text = "\n".join(citation_lines)

        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Sources:*\n{citation_text}",
                    }
                ],
            }
        )

    # Definitions section (if included)
    definitions = response.get("definitions", [])
    if definitions:
        blocks.append({"type": "divider"})

        # Group definitions text
        def_lines = []
        for defn in definitions:
            term = defn.get("term", "")
            definition = defn.get("definition", "")
            if term and definition:
                # Truncate long definitions for Slack
                if len(definition) > 200:
                    definition = definition[:197] + "..."
                def_lines.append(f"*{term}:* {definition}")

        if def_lines:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Definitions:*\n" + "\n".join(def_lines),
                    },
                }
            )

    # Footer with metadata
    metadata = response.get("metadata", {})
    latency_ms = metadata.get("latency_ms", 0)
    tokens_used = metadata.get("tokens_used", 0)
    chunks_retrieved = metadata.get("chunks_retrieved", 0)

    footer_parts = []
    if latency_ms:
        footer_parts.append(f"{latency_ms}ms")
    if tokens_used:
        footer_parts.append(f"{tokens_used} tokens")
    if chunks_retrieved:
        footer_parts.append(f"{chunks_retrieved} chunks")

    if footer_parts:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Response time: {' • '.join(footer_parts)}_",
                    }
                ],
            }
        )

    return blocks


def format_error_blocks(
    error_message: str, error_type: str = "ERROR"
) -> list[dict[str, Any]]:
    """Format error message into Slack Block Kit blocks.

    Args:
        error_message: The error message to display.
        error_type: Type of error (ERROR, WARNING, etc.).

    Returns:
        List of Block Kit block objects.
    """
    icon = ":x:" if error_type == "ERROR" else ":warning:"

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon} *{error_type}*\n\n{error_message}",
            },
        }
    ]
