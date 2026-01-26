# tests/conftest.py
"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_pdf(fixtures_dir: Path) -> Path:
    """Return path to sample PDF fixture."""
    return fixtures_dir / "information-policies-v5-04.pdf"


@pytest.fixture
def fee_list_pdf(fixtures_dir: Path) -> Path:
    """Return path to fee list PDF fixture."""
    return fixtures_dir / "january-2025-market-data-fee-list.pdf"
