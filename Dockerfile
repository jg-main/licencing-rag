# License Intelligence API - Production Dockerfile
# Base image: Python 3.13-slim (matches pyproject.toml requirement)
# Build tool: uv (fast Python package installer)
# Security: non-root user, minimal dependencies

# ============================================================================
# Stage 1: Builder - Install dependencies
# ============================================================================
FROM python:3.13-slim AS builder

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv with pinned version for reproducibility
# Using pip install instead of pipe-to-shell for supply-chain hardening
RUN pip install --no-cache-dir uv==0.5.18

# Set working directory
WORKDIR /build

# Copy dependency files (including uv.lock for reproducible builds)
COPY pyproject.toml uv.lock ./

# Export locked dependencies to requirements format and install to system site-packages
# --no-emit-project excludes the local package (only install dependencies)
# This ensures builds are fully lockfile-pinned for reproducibility
# Using --system to install to /usr/local (matches COPY strategy in runtime stage)
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    # Allow configurable workers for production scaling (default: 1)
    WORKERS=1

# Install runtime dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with configurable UID/GID for volume permissions
# Override at build time: --build-arg USER_UID=1000 --build-arg USER_GID=1000
# Logic: check username first, then verify UID/GID availability, fail on conflicts
ARG USER_UID=1000
ARG USER_GID=1000
RUN set -e && \
    # Handle group: use existing 'appuser' group, or create with requested GID if available
    if getent group appuser >/dev/null 2>&1; then \
    echo "Group 'appuser' already exists"; \
    elif getent group ${USER_GID} >/dev/null 2>&1; then \
    echo "ERROR: GID ${USER_GID} already in use by another group" && exit 1; \
    else \
    groupadd -g ${USER_GID} appuser; \
    fi && \
    # Handle user: use existing 'appuser' user, or create with requested UID if available
    if id appuser >/dev/null 2>&1; then \
    echo "User 'appuser' already exists"; \
    elif getent passwd ${USER_UID} >/dev/null 2>&1; then \
    echo "ERROR: UID ${USER_UID} already in use by another user" && exit 1; \
    else \
    useradd -u ${USER_UID} -g appuser --create-home --shell /bin/bash appuser; \
    fi

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser api/ ./api/
COPY --chown=appuser:appuser pyproject.toml ./

# Create directories for data, index, and logs
RUN mkdir -p /app/data /app/index /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port 8000
EXPOSE 8000

# Health check (every 30s, timeout 5s, start after 10s, max 3 retries)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run uvicorn server with configurable workers for production
# WORKERS env var controls concurrency (default: 1)
# For production: set WORKERS=4 or higher based on CPU cores
# Using exec to ensure proper signal handling (uvicorn becomes PID 1)
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS}"]
