# api/formatters/__init__.py
"""Formatters for different response formats (Slack, etc.)."""

from api.formatters.slack import format_answer_blocks

__all__ = ["format_answer_blocks"]
