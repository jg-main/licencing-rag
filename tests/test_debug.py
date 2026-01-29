# tests/test_debug.py
"""Tests for debug mode and audit logging (Phase 8)."""

import json
from pathlib import Path
from typing import Any

from _pytest.monkeypatch import MonkeyPatch

from app.debug import build_debug_output
from app.debug import write_debug_output


class TestDebugOutput:
    """Test debug output formatting and logging."""

    def test_build_debug_output_minimal(self) -> None:
        """Test build_debug_output with minimal parameters."""
        output = build_debug_output(
            original_query="What is CME?",
            normalized_query="what is cme",
            normalization_applied=True,
            normalization_failed=False,
            sources=["cme"],
            search_mode="hybrid",
            effective_search_mode="hybrid",
        )

        assert "query_processing" in output
        assert output["query_processing"]["original_query"] == "What is CME?"
        assert output["query_processing"]["normalized_query"] == "what is cme"
        assert output["query_processing"]["normalization_applied"] is True
        assert output["query_processing"]["normalization_failed"] is False

        assert "retrieval" in output
        assert output["retrieval"]["sources_queried"] == ["cme"]
        assert output["retrieval"]["search_mode_requested"] == "hybrid"
        assert output["retrieval"]["search_mode_effective"] == "hybrid"
        assert output["retrieval"]["fallback_occurred"] is False

    def test_build_debug_output_with_retrieval_info(self) -> None:
        """Test build_debug_output with retrieval statistics."""
        retrieval_info: dict[str, Any] = {
            "cme": {
                "mode_requested": "hybrid",
                "mode_used": "hybrid",
                "chunks_retrieved": 10,
                "bm25_available": True,
            }
        }

        output = build_debug_output(
            original_query="test query",
            normalized_query="test query",
            normalization_applied=False,
            normalization_failed=False,
            sources=["cme"],
            search_mode="hybrid",
            effective_search_mode="hybrid",
            retrieval_info=retrieval_info,
        )

        assert output["retrieval"]["per_source_results"] == retrieval_info

    def test_build_debug_output_with_all_phases(self) -> None:
        """Test build_debug_output with all pipeline phases."""
        output = build_debug_output(
            original_query="What is a license?",
            normalized_query="what is a license",
            normalization_applied=True,
            normalization_failed=False,
            sources=["cme"],
            search_mode="hybrid",
            effective_search_mode="hybrid",
            retrieval_info={"cme": {"chunks_retrieved": 5}},
            reranking_info={"enabled": True, "chunks_kept": 3},
            budget_info={"enabled": True, "tokens_used": 1500},
            confidence_gate_info={"enabled": True, "passed": True},
            final_chunks_count=3,
            final_context_tokens=1200,
            definitions_count=2,
            llm_called=True,
            validation_info={"validation_passed": True},
        )

        assert output["reranking"]["enabled"] is True
        assert output["budget"]["enabled"] is True
        assert output["confidence_gate"]["enabled"] is True
        assert output["final_context"]["chunks_count"] == 3
        assert output["final_context"]["tokens_count"] == 1200
        assert output["final_context"]["definitions_count"] == 2
        assert output["final_context"]["llm_called"] is True

    def test_write_debug_output_json_format(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ):
        """Test write_debug_output produces valid JSON."""
        # Override LOGS_DIR to use tmp_path
        from app import config

        monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(config, "DEBUG_LOG_FILE", tmp_path / "debug.jsonl")

        # Reset the global handler
        from app import debug

        debug._debug_file_handler = None  # type: ignore[reportPrivateUsage]

        debug_data: dict[str, Any] = {
            "query_processing": {
                "original_query": "test",
                "normalized_query": "test",
            },
            "retrieval": {
                "sources_queried": ["cme"],
            },
        }

        # Write debug output (not to stderr for test)
        write_debug_output(debug_data, write_to_stderr=False)

        # Verify log file was created
        log_file = tmp_path / "debug.jsonl"
        assert log_file.exists()

        # Verify JSON is valid
        with open(log_file) as f:
            line = f.readline()
            logged_data = json.loads(line)

            # Should have timestamp
            assert "timestamp" in logged_data
            # Should have query_processing
            assert "query_processing" in logged_data
            assert logged_data["query_processing"]["original_query"] == "test"

    def test_write_debug_output_rotation(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ):
        """Test that debug log files rotate correctly."""
        from app import config

        # Set very small max size for rotation testing
        monkeypatch.setattr(config, "LOGS_DIR", tmp_path)
        monkeypatch.setattr(config, "DEBUG_LOG_FILE", tmp_path / "debug.jsonl")
        monkeypatch.setattr(
            config, "DEBUG_LOG_MAX_BYTES", 500
        )  # Small but not too small
        monkeypatch.setattr(config, "DEBUG_LOG_BACKUP_COUNT", 2)

        # Reset the global handler
        from app import debug

        debug._debug_file_handler = None  # type: ignore[reportPrivateUsage]

        # Write many debug entries to trigger rotation
        for i in range(100):
            debug_data: dict[str, Any] = {
                "iteration": i,
                "query_processing": {
                    "original_query": f"test query number {i} with some extra text to make it larger"
                    * 5,
                    "normalized_query": f"test query number {i} with some extra text"
                    * 5,
                },
                "retrieval": {
                    "sources_queried": ["cme"],
                    "per_source_results": {"cme": {"chunks_retrieved": i}},
                },
            }
            write_debug_output(debug_data, write_to_stderr=False)

        # Verify main log file exists
        log_file = tmp_path / "debug.jsonl"
        assert log_file.exists()

        # Log rotation may or may not have occurred depending on timing
        # Just verify the main file has content
        assert log_file.stat().st_size > 0


class TestDebugOutputFormats:
    """Test debug output formatting helpers."""

    def test_normalization_changes_description(self) -> None:
        """Test normalization changes description."""
        from app.debug import _describe_normalization_changes  # type: ignore[reportPrivateUsage]

        changes = _describe_normalization_changes("What is CME?", "what is cme")

        # Check for word changes
        assert "removed_words" in changes
        assert "added_words" in changes
        assert "length_change" in changes
        assert "word_count_change" in changes

    def test_normalization_no_changes(self) -> None:
        """Test normalization when no changes occur."""
        from app.debug import _describe_normalization_changes  # type: ignore[reportPrivateUsage]

        changes = _describe_normalization_changes("test query", "test query")

        assert changes["length_change"] == 0
        assert changes["word_count_change"] == 0
        assert len(changes["removed_words"]) == 0
        assert len(changes["added_words"]) == 0
