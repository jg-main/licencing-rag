# api/config.py
"""Configuration constants for the License Intelligence REST API.

This module defines all configuration specific to the FastAPI REST API layer.
RAG-specific configuration remains in app/config.py.
"""

import os

# =============================================================================
# API Version
# =============================================================================

# API version for /version endpoint and OpenAPI docs
API_VERSION = "1.0.0"

# =============================================================================
# Authentication
# =============================================================================

# API key for authenticating requests to /query and /sources endpoints
# Must be provided as Bearer token in Authorization header
RAG_API_KEY = os.getenv("RAG_API_KEY")

# Slack signing secret for verifying /slack/command requests
# Used for HMAC-SHA256 signature verification
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Test mode flag - when enabled, skips authentication for /query and /sources
# SECURITY WARNING: Never set this to true in production!
# Only use for testing and development environments
RAG_TEST_MODE = os.getenv("RAG_TEST_MODE", "false").lower() in ("true", "1", "yes")

# =============================================================================
# Rate Limiting
# =============================================================================

# Maximum requests per minute per API key
RAG_RATE_LIMIT = int(os.getenv("RAG_RATE_LIMIT", "100"))

# =============================================================================
# CORS
# =============================================================================

# CORS allowed origins (comma-separated string, empty for none)
# Example: "https://example.com,https://app.example.com"
_cors_origins = os.getenv("RAG_CORS_ORIGINS", "")
RAG_CORS_ORIGINS: list[str] = [
    origin.strip() for origin in _cors_origins.split(",") if origin.strip()
]

# =============================================================================
# Proxy Configuration
# =============================================================================

# Trust proxy headers (X-Forwarded-For, X-Forwarded-Proto)
# Set to "true" only when running behind a trusted reverse proxy (e.g., ALB)
# When false, client IP is taken from the direct connection only
TRUST_PROXY_HEADERS = os.getenv("RAG_TRUST_PROXY_HEADERS", "false").lower() == "true"
