# app/output.py
"""Output formatters for the License Intelligence System.

This module provides output formatting for query results:
- Console output using Rich library with panels, tables, and markdown
- JSON output with structured schema for programmatic consumption

Usage:
    from app.output import format_console, format_json

    result = query("What are the fees?")
    print(format_console(result))  # Rich formatted string
    print(format_json(result))     # JSON string
"""

import json
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import Enum
from io import StringIO
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.theme import Theme


class OutputFormat(Enum):
    """Supported output formats."""

    CONSOLE = "console"
    JSON = "json"


# Custom theme for console output
CONSOLE_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "provider": "cyan bold",
        "document": "green",
        "section": "yellow",
        "page": "magenta",
        "term": "cyan",
        "definition": "white",
        "dim": "dim",
    }
)


@dataclass
class QueryResult:
    """Structured query result for output formatting.

    This dataclass provides a typed interface for query results,
    making the output formatters more robust.
    """

    answer: str
    context: str
    citations: list[dict[str, Any]]
    definitions: list[dict[str, Any]]
    chunks_retrieved: int
    providers: list[str]
    search_mode: str
    effective_search_mode: str
    debug_info: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryResult":
        """Create a QueryResult from a dictionary.

        Args:
            data: Dictionary with query result data.

        Returns:
            QueryResult instance.
        """
        return cls(
            answer=data.get("answer", ""),
            context=data.get("context", ""),
            citations=data.get("citations", []),
            definitions=data.get("definitions", []),
            chunks_retrieved=data.get("chunks_retrieved", 0),
            providers=data.get("providers", []),
            search_mode=data.get("search_mode", ""),
            effective_search_mode=data.get("effective_search_mode", ""),
            debug_info=data.get("debug_info"),
        )


def format_console(result: dict[str, Any]) -> str:
    """Format query result for console output using Rich.

    Produces beautifully formatted output with:
    - Answer panel with markdown rendering
    - Source documents table with provider, document, section, and page info
    - Auto-linked definitions table (if any)
    - Search mode and retrieval statistics

    Args:
        result: Query result dictionary from query().

    Returns:
        Formatted string for console display.
    """
    # Create a console that writes to a string buffer
    string_buffer = StringIO()
    console = Console(file=string_buffer, force_terminal=True, theme=CONSOLE_THEME)

    qr = QueryResult.from_dict(result)

    # Header with provider info
    provider_label = ", ".join(p.upper() for p in qr.providers) if qr.providers else ""
    title = f"RESPONSE (Sources: {provider_label})" if provider_label else "RESPONSE"

    console.print()

    # Answer panel with markdown
    answer_md = Markdown(qr.answer)
    console.print(
        Panel(
            answer_md,
            title=f"[bold blue]{title}[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # Search mode info if different from requested
    if qr.effective_search_mode and qr.effective_search_mode != qr.search_mode:
        console.print(
            f"\n[warning]Note: Search mode fell back from "
            f"'{qr.search_mode}' to '{qr.effective_search_mode}'[/warning]"
        )

    # Debug info if available
    if qr.debug_info:
        console.print()
        console.rule("[dim]Debug Information[/dim]")
        console.print(
            f"[dim]Original query: {qr.debug_info.get('original_query', 'N/A')}[/dim]"
        )
        console.print(
            f"[dim]Normalized query: {qr.debug_info.get('normalized_query', 'N/A')}[/dim]"
        )
        retrieval_sources = qr.debug_info.get("retrieval_sources", {})
        if retrieval_sources:
            console.print(
                f"[dim]Retrieval sources: "
                f"vector={retrieval_sources.get('vector', 0)}, "
                f"keyword={retrieval_sources.get('keyword', 0)}, "
                f"hybrid={retrieval_sources.get('hybrid', 0)}[/dim]"
            )

    # Source Information section
    console.print()
    console.rule("[dim]Source Information[/dim]")
    console.print(
        f"[dim]Retrieved {qr.chunks_retrieved} chunks | "
        f"Search mode: {qr.effective_search_mode or qr.search_mode}[/dim]"
    )

    # Citations table
    if qr.citations:
        console.print()
        citations_table = Table(
            title="Source Documents",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        citations_table.add_column("Provider", style="provider", width=10)
        citations_table.add_column("Document", style="document")
        citations_table.add_column("Section", style="section")
        citations_table.add_column("Pages", style="page", justify="right")

        for cit in qr.citations:
            provider = cit.get("provider", "").upper()
            page_start = cit.get("page_start", "?")
            page_end = cit.get("page_end", page_start)
            if page_start != page_end and page_end != "?":
                page_str = f"{page_start}–{page_end}"
            else:
                page_str = str(page_start)

            citations_table.add_row(
                provider,
                cit.get("document", ""),
                cit.get("section", "N/A"),
                page_str,
            )

        console.print(citations_table)

    # Definitions table
    if qr.definitions:
        console.print()
        def_table = Table(
            title="Auto-Linked Definitions",
            show_header=True,
            header_style="bold",
            border_style="dim",
        )
        def_table.add_column("Term", style="term", width=20)
        def_table.add_column("Definition", style="definition")
        def_table.add_column("Source", style="dim", max_width=40)

        for defn in qr.definitions:
            # Truncate long definitions for display
            definition_text = defn.get("definition", "")
            if len(definition_text) > 100:
                definition_text = definition_text[:97] + "..."

            source = defn.get("document_path", defn.get("document", ""))

            def_table.add_row(
                defn.get("term", ""),
                definition_text,
                source,
            )

        console.print(def_table)

    # Debug information (if present)
    debug_info = result.get("debug")
    if debug_info:
        console.print()
        console.rule("[dim]Debug Information[/dim]")

        debug_items = [
            ("Original Query", debug_info["original_query"]),
            ("Normalized Query", debug_info["normalized_query"]),
            (
                "Normalization Applied",
                "Yes" if debug_info["normalization_applied"] else "No",
            ),
        ]

        if debug_info.get("normalization_failed"):
            debug_items.append(
                (
                    "⚠ Normalization Status",
                    "[yellow]Failed - using original query[/yellow]",
                )
            )

        debug_table = Table(show_header=False, border_style="dim", box=None)
        debug_table.add_column("Key", style="dim", width=25)
        debug_table.add_column("Value")

        for key, value in debug_items:
            debug_table.add_row(key, str(value))

        console.print(debug_table)

    console.print()

    return string_buffer.getvalue()


def format_json(result: dict[str, Any], pretty: bool = True) -> str:
    """Format query result as structured JSON.

    Produces a JSON output with the following schema:
    {
        "answer": "string",
        "supporting_clauses": [...],
        "definitions": [...],
        "citations": [...],
        "metadata": {
            "providers": [...],
            "chunks_retrieved": int,
            "search_mode": "string",
            "effective_search_mode": "string",
            "timestamp": "ISO-8601 string"
        }
    }

    Args:
        result: Query result dictionary from query().
        pretty: If True, format with indentation. Default True.

    Returns:
        JSON string.
    """
    qr = QueryResult.from_dict(result)

    # Build structured output
    output = {
        "answer": qr.answer,
        "supporting_clauses": _extract_clauses(qr.context),
        "definitions": [
            {
                "term": d.get("term", ""),
                "definition": d.get("definition", ""),
                "source": {
                    "provider": d.get("provider", ""),
                    "document": d.get("document_path", d.get("document", "")),
                    "section": d.get("section", ""),
                    "page_start": d.get("page_start"),
                    "page_end": d.get("page_end"),
                },
            }
            for d in qr.definitions
        ],
        "citations": [
            {
                "provider": c.get("provider", ""),
                "document": c.get("document", ""),
                "section": c.get("section", ""),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
            }
            for c in qr.citations
        ],
        "metadata": {
            "providers": qr.providers,
            "chunks_retrieved": qr.chunks_retrieved,
            "search_mode": qr.search_mode,
            "effective_search_mode": qr.effective_search_mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Include debug information if present
    debug_info = result.get("debug")
    if debug_info:
        output["debug"] = {
            "original_query": debug_info["original_query"],
            "normalized_query": debug_info["normalized_query"],
            "normalization_applied": debug_info["normalization_applied"],
            "normalization_failed": debug_info.get("normalization_failed", False),
        }

    if pretty:
        return json.dumps(output, indent=2, ensure_ascii=False)
    return json.dumps(output, ensure_ascii=False)


def _extract_clauses(context: str) -> list[dict[str, Any]]:
    """Extract supporting clauses from context string.

    Parses the formatted context string to extract individual clauses
    with their source information.

    Args:
        context: Formatted context string from query().

    Returns:
        List of clause dictionaries with text and source info.
    """
    if not context:
        return []

    clauses = []
    # Split on the context header pattern
    # Format: --- [PROVIDER] Document | Section | Pages X-Y ---
    import re

    pattern = (
        r"---\s*\[([^\]]+)\]\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^-]+(?:-[^-]+)?)\s*---"
    )
    parts = re.split(pattern, context)

    # parts will be: [empty, provider, doc, section, pages, text, provider, doc, ...]
    i = 1
    while i < len(parts):
        if i + 4 < len(parts):
            provider = parts[i].strip()
            document = parts[i + 1].strip()
            section = parts[i + 2].strip()
            pages_str = parts[i + 3].strip()
            text = parts[i + 4].strip() if i + 4 < len(parts) else ""

            # Parse page range (matches "Page 5" or "Pages 10-12")
            page_start = None
            page_end = None
            pages_match = re.search(r"Pages?\s*(\d+)(?:-(\d+))?", pages_str)
            if pages_match:
                page_start = int(pages_match.group(1))
                page_end = (
                    int(pages_match.group(2)) if pages_match.group(2) else page_start
                )

            if text:
                clauses.append(
                    {
                        "text": text,
                        "source": {
                            "provider": provider,
                            "document": document,
                            "section": section,
                            "page_start": page_start,
                            "page_end": page_end,
                        },
                    }
                )
            i += 5
        else:
            break

    return clauses


def print_result(
    result: dict[str, Any],
    output_format: OutputFormat,
    show_definitions: bool = False,
) -> None:
    """Print query result in the specified format.

    Convenience function that formats and prints the result directly.

    Args:
        result: Query result dictionary from query().
        output_format: Output format to use.
        show_definitions: Whether to display auto-linked definitions.
    """
    if output_format == OutputFormat.JSON:
        print(format_json(result))
    else:
        # For console output, use a real console for proper rendering
        console = Console(theme=CONSOLE_THEME)

        qr = QueryResult.from_dict(result)

        # Header with provider info
        provider_label = (
            ", ".join(p.upper() for p in qr.providers) if qr.providers else ""
        )
        title = (
            f"RESPONSE (Sources: {provider_label})" if provider_label else "RESPONSE"
        )

        console.print()

        # Answer panel with markdown
        answer_md = Markdown(qr.answer)
        console.print(
            Panel(
                answer_md,
                title=f"[bold blue]{title}[/bold blue]",
                border_style="blue",
                padding=(1, 2),
            )
        )

        # Search mode info if different from requested
        if qr.effective_search_mode and qr.effective_search_mode != qr.search_mode:
            console.print(
                f"\n[warning]Note: Search mode fell back from "
                f"'{qr.search_mode}' to '{qr.effective_search_mode}'[/warning]"
            )

        # Source Information section
        console.print()
        console.rule("[dim]Source Information[/dim]")
        console.print(
            f"[dim]Retrieved {qr.chunks_retrieved} chunks | "
            f"Search mode: {qr.effective_search_mode or qr.search_mode}[/dim]"
        )

        # Citations table
        if qr.citations:
            console.print()
            citations_table = Table(
                title="Source Documents",
                show_header=True,
                header_style="bold",
                border_style="dim",
            )
            citations_table.add_column("Provider", style="provider", width=10)
            citations_table.add_column("Document", style="document")
            citations_table.add_column("Section", style="section")
            citations_table.add_column("Pages", style="page", justify="right")

            for cit in qr.citations:
                provider = cit.get("provider", "").upper()
                page_start = cit.get("page_start", "?")
                page_end = cit.get("page_end", page_start)
                if page_start != page_end and page_end != "?":
                    page_str = f"{page_start}–{page_end}"
                else:
                    page_str = str(page_start)

                citations_table.add_row(
                    provider,
                    cit.get("document", ""),
                    cit.get("section", "N/A"),
                    page_str,
                )

            console.print(citations_table)

        # Definitions table
        if show_definitions and qr.definitions:
            console.print()
            def_table = Table(
                title="Auto-Linked Definitions",
                show_header=True,
                header_style="bold",
                border_style="dim",
            )
            def_table.add_column("Term", style="term", width=20)
            def_table.add_column("Definition", style="definition")
            def_table.add_column("Source", style="dim", max_width=40)

            for defn in qr.definitions:
                # Truncate long definitions for display
                definition_text = defn.get("definition", "")
                if len(definition_text) > 100:
                    definition_text = definition_text[:97] + "..."

                source = defn.get("document_path", defn.get("document", ""))

                def_table.add_row(
                    defn.get("term", ""),
                    definition_text,
                    source,
                )

            console.print(def_table)

        # Debug information (if present)
        debug_info = result.get("debug")
        if debug_info:
            console.print()
            console.rule("[dim]Debug Information[/dim]")

            debug_items = [
                ("Original Query", debug_info["original_query"]),
                ("Normalized Query", debug_info["normalized_query"]),
                (
                    "Normalization Applied",
                    "Yes" if debug_info["normalization_applied"] else "No",
                ),
            ]

            if debug_info.get("normalization_failed"):
                debug_items.append(
                    (
                        "⚠ Normalization Status",
                        "[yellow]Failed - using original query[/yellow]",
                    )
                )

            debug_table = Table(show_header=False, border_style="dim", box=None)
            debug_table.add_column("Key", style="dim", width=25)
            debug_table.add_column("Value")

            for key, value in debug_items:
                debug_table.add_row(key, str(value))

            console.print(debug_table)

        console.print()
