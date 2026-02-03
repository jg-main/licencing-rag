# tests/conftest.py
"""Pytest configuration and shared fixtures."""

from pathlib import Path
from unittest.mock import patch

import pytest

# Test API key used across all API tests
TEST_API_KEY = "test-api-key-12345"


@pytest.fixture(autouse=True, scope="function")
def enable_test_mode(request):
    """Enable test mode for most API tests, but skip for auth tests.

    This fixture automatically enables RAG_TEST_MODE to bypass authentication
    during tests. This is safer than setting RAG_API_KEY to None since it
    requires an explicit flag to disable auth.

    Auth-specific tests disable this fixture with markers to test authentication properly.
    """
    # Skip test mode for tests marked with pytest.mark.requires_auth
    if "requires_auth" in request.keywords:
        yield False
    else:
        with patch("api.config.RAG_TEST_MODE", True):
            yield True


@pytest.fixture(autouse=True, scope="function")
def reset_rate_limiter():
    """Reset the global rate limiter before each test.

    This prevents rate limit exhaustion from affecting tests that don't
    explicitly test rate limiting behavior.
    """
    # Import here to avoid circular dependencies
    import api.middleware.rate_limit

    # Reset the global rate limiter before each test
    api.middleware.rate_limit._rate_limiter = api.middleware.rate_limit.RateLimiter()
    yield
    # Reset again after test to clean up
    api.middleware.rate_limit._rate_limiter = api.middleware.rate_limit.RateLimiter()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return authentication headers for API requests.

    Use this fixture when testing authentication specifically.
    Most tests don't need this since auth is disabled in test environment.
    """
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


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


@pytest.fixture
def sample_docx(fixtures_dir: Path) -> Path:
    """Return path to sample DOCX fixture with tables."""
    return fixtures_dir / "sample-agreement.docx"
