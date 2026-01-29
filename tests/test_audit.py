# tests/test_audit.py
"""Tests for query/response audit logging (Phase 8.2)."""

import json
import time
from pathlib import Path

import pytest


class TestAuditLogging:
    """Test query/response audit logging functionality."""

    @pytest.fixture(autouse=True)
    def reset_handler(self) -> None:
        """Reset the global audit handler before each test."""
        from app.audit import _reset_handler

        _reset_handler()

    def test_audit_log_file_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that audit log file is created on first write."""
        from app.audit import log_query_response

        # Set up temporary logs directory
        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        # Log a query
        log_query_response(
            query="test query",
            answer="test answer",
            sources=["cme"],
            chunks_retrieved=10,
            chunks_used=3,
            tokens_input=100,
            tokens_output=50,
            latency_ms=1500,
            refused=False,
            refusal_reason=None,
            user_id=None,
            write_to_console=False,
        )

        # Verify file was created
        assert audit_file.exists()
        assert audit_file.stat().st_size > 0

    def test_audit_log_json_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that audit log entries are valid JSON."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="What are the fees?",
            answer="The fees are $10/month.",
            sources=["cme"],
            chunks_retrieved=12,
            chunks_used=4,
            tokens_input=200,
            tokens_output=75,
            latency_ms=2000,
            refused=False,
            refusal_reason=None,
            user_id=None,
            write_to_console=False,
        )

        # Read and parse the log entry
        content = audit_file.read_text()
        log_entry = json.loads(content.strip())

        # Verify required fields
        assert "timestamp" in log_entry
        assert log_entry["query"] == "What are the fees?"
        assert log_entry["answer"] == "The fees are $10/month."
        assert log_entry["sources"] == ["cme"]
        assert log_entry["chunks_retrieved"] == 12
        assert log_entry["chunks_used"] == 4
        assert log_entry["tokens_input"] == 200
        assert log_entry["tokens_output"] == 75
        assert log_entry["latency_ms"] == 2000
        assert log_entry["refused"] is False
        assert log_entry["refusal_reason"] is None
        assert log_entry["user_id"] is None

    def test_audit_log_refusal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that refusals are logged correctly."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="Vague question",
            answer="I cannot answer this question...",
            sources=["cme"],
            chunks_retrieved=5,
            chunks_used=0,
            tokens_input=0,
            tokens_output=0,
            latency_ms=500,
            refused=True,
            refusal_reason="insufficient_confidence",
            user_id=None,
            write_to_console=False,
        )

        content = audit_file.read_text()
        log_entry = json.loads(content.strip())

        assert log_entry["refused"] is True
        assert log_entry["refusal_reason"] == "insufficient_confidence"
        assert log_entry["chunks_used"] == 0

    def test_audit_log_multiple_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that multiple queries create separate JSONL lines."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        # Log three queries
        for i in range(3):
            log_query_response(
                query=f"Query {i}",
                answer=f"Answer {i}",
                sources=["cme"],
                chunks_retrieved=10,
                chunks_used=3,
                tokens_input=100 + i,
                tokens_output=50 + i,
                latency_ms=1000 + i * 100,
                refused=False,
                refusal_reason=None,
                user_id=None,
                write_to_console=False,
            )

        # Read all entries
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 3

        # Verify each line is valid JSON
        for i, line in enumerate(lines):
            entry = json.loads(line)
            assert entry["query"] == f"Query {i}"
            assert entry["answer"] == f"Answer {i}"
            assert entry["tokens_input"] == 100 + i

    def test_audit_log_with_user_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test logging with user_id for future API authentication."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="Test query",
            answer="Test answer",
            sources=["cme"],
            chunks_retrieved=10,
            chunks_used=3,
            tokens_input=100,
            tokens_output=50,
            latency_ms=1500,
            refused=False,
            refusal_reason=None,
            user_id="user123",
            write_to_console=False,
        )

        content = audit_file.read_text()
        log_entry = json.loads(content.strip())

        assert log_entry["user_id"] == "user123"

    def test_calculate_latency_ms(self) -> None:
        """Test latency calculation function."""
        from app.audit import calculate_latency_ms

        start = time.time()
        time.sleep(0.1)  # Sleep for 100ms
        latency = calculate_latency_ms(start)

        # Should be approximately 100ms (allow ±20ms tolerance)
        assert 80 <= latency <= 120

    def test_audit_log_console_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that console output is written to stderr when requested."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="Test query",
            answer="Test answer",
            sources=["cme"],
            chunks_retrieved=10,
            chunks_used=3,
            tokens_input=100,
            tokens_output=50,
            latency_ms=1500,
            refused=False,
            refusal_reason=None,
            user_id=None,
            write_to_console=True,  # Enable console output
        )

        captured = capsys.readouterr()
        assert "AUDIT LOG" in captured.err
        assert "Test query" in captured.err
        assert "Test answer" in captured.err

    def test_audit_log_no_console_output_by_default(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that console output is NOT written by default."""
        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="Test query",
            answer="Test answer",
            sources=["cme"],
            chunks_retrieved=10,
            chunks_used=3,
            tokens_input=100,
            tokens_output=50,
            latency_ms=1500,
            refused=False,
            refusal_reason=None,
            user_id=None,
            write_to_console=False,  # Default - no console output
        )

        captured = capsys.readouterr()
        assert "AUDIT LOG" not in captured.err
        assert "Test query" not in captured.err

        # But file should still be written
        assert audit_file.exists()

    def test_audit_log_timestamp_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that timestamps are in ISO 8601 UTC format."""
        from datetime import datetime

        from app.audit import log_query_response

        logs_dir = tmp_path / "logs"
        audit_file = logs_dir / "queries.jsonl"

        monkeypatch.setattr("app.config.LOGS_DIR", logs_dir)
        monkeypatch.setattr("app.config.AUDIT_LOG_FILE", audit_file)
        monkeypatch.setattr("app.config.AUDIT_LOG_MAX_BYTES", 10 * 1024 * 1024)
        monkeypatch.setattr("app.config.AUDIT_LOG_BACKUP_COUNT", 10)

        log_query_response(
            query="Test",
            answer="Test",
            sources=["cme"],
            chunks_retrieved=1,
            chunks_used=1,
            tokens_input=10,
            tokens_output=10,
            latency_ms=100,
            write_to_console=False,
        )

        content = audit_file.read_text()
        log_entry = json.loads(content.strip())

        # Verify ISO 8601 format
        timestamp = log_entry["timestamp"]
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp or "-" in timestamp[-6:]

        # Verify it can be parsed
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
