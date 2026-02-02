# Deployment Implementation Plan - License Intelligence API

**Version:** 1.0\
**Created:** 2026-02-02\
**Updated:** 2026-02-02\
**Target:** deployment-specs.md\
**Branch:** openai

______________________________________________________________________

## Overview

This plan implements a **FastAPI REST API** layer on top of the existing License Intelligence RAG system, enabling Slack app integration and programmatic access to licensing document queries.

### Key Deliverables

- **FastAPI Application**: REST endpoints wrapping existing RAG functionality
- **Authentication**: API key + Slack signature verification
- **Docker Deployment**: Containerized application for AWS EC2
- **Slack Integration**: Dedicated endpoint for slash commands

### Dependencies

- Existing RAG system (Phases 1-10 complete)
- OpenAI API access configured
- AWS EC2 instance (for deployment)
- Slack app credentials (for Slack integration)

______________________________________________________________________

## Progress Checklist

> Update this checklist as tasks are completed. Use `[x]` to mark done.

### Phase 1: Project Setup ⏳

**Status**: ⏳ **NOT STARTED**

#### 1.1 Directory Structure

- [ ] Create `api/` directory
- [ ] Create `api/__init__.py`
- [ ] Create `api/main.py` (FastAPI app entry point)
- [ ] Create `api/routes/` directory for route modules
- [ ] Create `api/middleware/` directory for middleware
- [ ] Create `api/models/` directory for Pydantic schemas

#### 1.2 Dependencies

- [ ] Add `fastapi` to pyproject.toml
- [ ] Add `uvicorn[standard]` to pyproject.toml
- [ ] Add `python-multipart` for form data (Slack)
- [ ] Add `httpx` for async HTTP client (Slack response_url)
- [ ] Run `uv sync` to install dependencies
- [ ] Verify imports work correctly

#### 1.3 Configuration

- [ ] Add API configuration to `app/config.py`:
  - [ ] `RAG_API_KEY` environment variable
  - [ ] `SLACK_SIGNING_SECRET` environment variable
  - [ ] `RAG_RATE_LIMIT` (default: 100)
  - [ ] `RAG_CORS_ORIGINS` (default: empty/none)
  - [ ] `API_VERSION` constant
- [ ] Create `.env.example` with all required variables
- [ ] Update README with API configuration section

#### 1.4 Verification

- [ ] `uv sync` completes without errors
- [ ] `python -c "from api.main import app"` works
- [ ] All existing tests still pass

______________________________________________________________________

### Phase 2: Core API Implementation ⏳

**Status**: ⏳ **NOT STARTED**

#### 2.1 Pydantic Models

Create request/response schemas in `api/models/`:

- [ ] Create `api/models/__init__.py`
- [ ] Create `api/models/requests.py`:
  - [ ] `QueryRequest` model with validation
  - [ ] `QueryOptions` model (search_mode, top_k, etc.)
- [ ] Create `api/models/responses.py`:
  - [ ] `HealthResponse` model
  - [ ] `ReadyResponse` model with checks
  - [ ] `VersionResponse` model
  - [ ] `QueryResponse` model with citations
  - [ ] `ErrorResponse` model with code/message/details
  - [ ] `SourcesResponse` model
  - [ ] `SourceDocumentsResponse` model
- [ ] Add field validators (question not empty, sources valid, etc.)

#### 2.2 Health Endpoints

Create `api/routes/health.py`:

- [ ] Implement `GET /health` endpoint
  - [ ] Return status and timestamp
  - [ ] No authentication required
- [ ] Implement `GET /ready` endpoint
  - [ ] Check ChromaDB index exists
  - [ ] Check BM25 index exists
  - [ ] Check OpenAI API key configured (presence only)
  - [ ] Return individual check results
- [ ] Implement `GET /version` endpoint
  - [ ] Return API version
  - [ ] Return RAG version
  - [ ] Return model information

#### 2.3 Query Endpoint

Create `api/routes/query.py`:

- [ ] Implement `POST /query` endpoint
- [ ] Parse and validate `QueryRequest`
- [ ] Map request to `app.query.query()` parameters:
  - [ ] `question` → `question`
  - [ ] `sources` → `sources`
  - [ ] `options.search_mode` → `search_mode`
  - [ ] `options.top_k` → `top_k`
  - [ ] `options.enable_reranking` → `enable_reranking`
  - [ ] `options.enable_confidence_gate` → `enable_confidence_gate`
  - [ ] `options.include_definitions` → `show_definitions` (map in response)
- [ ] Call `app.query.query()` with parameters
- [ ] Transform result to `QueryResponse` format
- [ ] Handle refused queries (success=true, refused=true)
- [ ] Generate unique `query_id` (UUID)
- [ ] Include metadata (tokens, latency, chunks)

#### 2.4 Sources Endpoints

Create `api/routes/sources.py`:

- [ ] Implement `GET /sources` endpoint
  - [ ] List all configured sources from `app.config.SOURCES`
  - [ ] Include document count per source
  - [ ] Include status (active/planned)
- [ ] Implement `GET /sources/{name}` endpoint
  - [ ] Validate source exists (404 if not)
  - [ ] Call `app.ingest.list_indexed_documents()`
  - [ ] Return document list with count

#### 2.5 FastAPI Application

Create `api/main.py`:

- [ ] Initialize FastAPI app with metadata
- [ ] Configure CORS middleware
- [ ] Register health routes
- [ ] Register query routes
- [ ] Register sources routes
- [ ] Add request ID middleware
- [ ] Add request logging middleware
- [ ] Configure OpenAPI documentation

#### 2.6 Verification

- [ ] `uvicorn api.main:app --reload` starts successfully
- [ ] `/health` returns 200 with status
- [ ] `/ready` returns check results
- [ ] `/version` returns version info
- [ ] `/docs` shows OpenAPI documentation
- [ ] Create `tests/test_api_health.py` with basic tests
- [ ] All tests pass

______________________________________________________________________

### Phase 3: Error Handling ⏳

**Status**: ⏳ **NOT STARTED**

#### 3.1 Exception Classes

Create `api/exceptions.py`:

- [ ] `APIError` base exception with code, message, details
- [ ] `ValidationError` (400)
- [ ] `EmptyQuestionError` (400)
- [ ] `UnauthorizedError` (401)
- [ ] `ForbiddenError` (403)
- [ ] `SourceNotFoundError` (404)
- [ ] `RateLimitError` (429)
- [ ] `OpenAIError` (502)
- [ ] `ServiceUnavailableError` (503)

#### 3.2 Exception Handlers

Update `api/main.py`:

- [ ] Add global exception handler for `APIError`
- [ ] Add handler for `RequestValidationError` (Pydantic)
- [ ] Add handler for `Exception` (catch-all, 500)
- [ ] Add handler for OpenAI API errors
- [ ] Ensure all errors return consistent `ErrorResponse` format
- [ ] Include `request_id` in error responses

#### 3.3 Request Validation

- [ ] Validate empty request body → `VALIDATION_ERROR`
- [ ] Validate empty question → `EMPTY_QUESTION`
- [ ] Validate whitespace-only question → `EMPTY_QUESTION`
- [ ] Validate invalid sources → `SOURCE_NOT_FOUND`
- [ ] Validate search_mode values → `VALIDATION_ERROR`
- [ ] Validate top_k range (1-50) → `VALIDATION_ERROR`

#### 3.4 Verification

- [ ] Create `tests/test_api_errors.py`
- [ ] Test empty request returns 400 with correct code
- [ ] Test empty question returns 400 with `EMPTY_QUESTION`
- [ ] Test invalid source returns 404 with `SOURCE_NOT_FOUND`
- [ ] Test invalid JSON returns 400
- [ ] Test internal errors return 500 with `INTERNAL_ERROR`
- [ ] All error responses match documented format

______________________________________________________________________

### Phase 4: Authentication ⏳

**Status**: ⏳ **NOT STARTED**

#### 4.1 API Key Authentication

Create `api/middleware/auth.py`:

- [ ] Implement `get_api_key()` dependency
- [ ] Extract Bearer token from `Authorization` header
- [ ] Validate against `RAG_API_KEY` environment variable
- [ ] Raise `UnauthorizedError` if missing/invalid
- [ ] Skip auth for health endpoints (`/health`, `/ready`, `/version`)

#### 4.2 Slack Signature Verification

Add to `api/middleware/auth.py`:

- [ ] Implement `verify_slack_signature()` function
- [ ] Extract `X-Slack-Signature` header
- [ ] Extract `X-Slack-Request-Timestamp` header
- [ ] Validate timestamp within 5 minutes (replay protection)
- [ ] Compute HMAC-SHA256 signature
- [ ] Compare using `hmac.compare_digest()`
- [ ] Raise `UnauthorizedError` if invalid

#### 4.3 Combined Authentication

Create `api/dependencies.py`:

- [ ] Implement `authenticate()` dependency
- [ ] Use path-based auth:
  - [ ] `/slack/command` → verify Slack signature only
  - [ ] `/query`, `/sources` → verify Bearer token only
- [ ] Return authentication context (type: "api_key" | "slack")

#### 4.4 Apply Authentication

- [ ] Add `authenticate` dependency to `/query` endpoint
- [ ] Add `authenticate` dependency to `/sources` endpoints
- [ ] Keep health endpoints public (no auth)
- [ ] Log authentication type in request logs

#### 4.5 Verification

- [ ] Create `tests/test_api_auth.py`
- [ ] Test request without auth returns 401
- [ ] Test invalid API key returns 401
- [ ] Test valid API key returns 200
- [ ] Test invalid Slack signature returns 401 (Slack endpoint)
- [ ] Test expired Slack timestamp returns 401 (Slack endpoint)
- [ ] Test valid Slack signature returns 200 (Slack endpoint)
- [ ] Test health endpoints work without auth

______________________________________________________________________

### Phase 5: Rate Limiting ⏳

**Status**: ⏳ **NOT STARTED**

#### 5.1 Rate Limiter Implementation

Create `api/middleware/rate_limit.py`:

- [ ] Implement rate limiter (in-memory for single instance only)
- [ ] Add Redis-backed option for multi-instance or multi-worker deployments
- [ ] Track requests by API key
- [ ] Track requests by IP (fallback for Slack)
- [ ] Configure limit from `RAG_RATE_LIMIT` env var
- [ ] Default: 100 requests per minute per key
- [ ] Support burst limit (10 concurrent requests)

#### 5.2 Rate Limit Headers

- [ ] Add `X-RateLimit-Limit` header to responses
- [ ] Add `X-RateLimit-Remaining` header to responses
- [ ] Add `X-RateLimit-Reset` header to responses
- [ ] Add `Retry-After` header on 429 responses

#### 5.3 Rate Limit Middleware

- [ ] Create rate limit dependency
- [ ] Apply to `/query` endpoint
- [ ] Apply to `/sources` endpoints
- [ ] Skip for health endpoints
- [ ] Return `RateLimitError` when exceeded

#### 5.4 Verification

- [ ] Create `tests/test_api_rate_limit.py`
- [ ] Test rate limit headers present
- [ ] Test exceeding limit returns 429
- [ ] Test limit resets after window
- [ ] Test different API keys have separate limits

______________________________________________________________________

### Phase 6: Slack Integration ⏳

**Status**: ⏳ **NOT STARTED**

#### 6.1 Slack Endpoint

Create `api/routes/slack.py`:

- [ ] Implement `POST /slack/command` endpoint
- [ ] Parse `application/x-www-form-urlencoded` payload
- [ ] Extract `text` field as question
- [ ] Extract `user_id` for audit logging
- [ ] Extract `response_url` for async response
- [ ] Validate Slack signature (use auth middleware; no API key required)

#### 6.2 Immediate Response

- [ ] Return immediate acknowledgment (< 3 seconds)
- [ ] Use `response_type: "ephemeral"` for acknowledgment
- [ ] Include "Searching..." message
- [ ] Store `response_url` for async response

#### 6.3 Async Response

- [ ] Create background task for query processing
- [ ] Call `app.query.query()` with extracted question
- [ ] Format response using Slack Block Kit
- [ ] Send response to `response_url` via HTTP POST
- [ ] Handle errors gracefully (send error message to Slack)

#### 6.4 Block Kit Formatting

Create `api/formatters/slack.py`:

- [ ] Implement `format_answer_blocks()` function
- [ ] Create answer section with markdown
- [ ] Create citations context block
- [ ] Create definitions section (if included)
- [ ] Handle refusal formatting
- [ ] Add footer with query metadata

#### 6.5 Verification

- [ ] Create `tests/test_api_slack.py`
- [ ] Test slash command payload parsing
- [ ] Test immediate acknowledgment response
- [ ] Test async response formatting
- [ ] Test error handling in async response
- [ ] Manual test with actual Slack app (integration)

______________________________________________________________________

### Phase 7: Docker Configuration ⏳

**Status**: ⏳ **NOT STARTED**

#### 7.1 Dockerfile

- [ ] Create `Dockerfile` in project root
- [ ] Use a Python base image that matches `pyproject.toml` (e.g., `python:3.13-slim`)
- [ ] Set environment variables (PYTHONUNBUFFERED, etc.)
- [ ] Install system dependencies (build-essential, curl for HEALTHCHECK)
- [ ] Install uv package manager
- [ ] Copy and install Python dependencies
- [ ] Copy application code (`app/`, `api/`)
- [ ] Create non-root user (`appuser`)
- [ ] Set working directory and user
- [ ] Expose port 8000
- [ ] Add HEALTHCHECK instruction
- [ ] Set CMD for uvicorn

#### 7.2 Docker Compose

- [ ] Create `docker-compose.yml`
- [ ] Define `api` service
- [ ] Configure environment variables from `.env`
- [ ] Mount volumes for data, index, logs
- [ ] Configure health check
- [ ] Set restart policy (`unless-stopped`)
- [ ] Configure port mapping (8000:8000)

#### 7.3 Docker Ignore

- [ ] Create `.dockerignore` file
- [ ] Exclude `.git/`
- [ ] Exclude `__pycache__/`
- [ ] Exclude `.pytest_cache/`
- [ ] Exclude `*.pyc`
- [ ] Exclude `.env` (use env vars instead)
- [ ] Exclude `logs/` (mount as volume)
- [ ] Exclude `tests/`
- [ ] Exclude `eval/`
- [ ] Exclude `docs/`

#### 7.4 Verification

- [ ] `docker build -t rag-api:latest .` succeeds
- [ ] `docker run` starts container
- [ ] Health check passes
- [ ] `/health` endpoint accessible
- [ ] `/query` endpoint works with auth
- [ ] Logs written to mounted volume
- [ ] Container runs as non-root user

______________________________________________________________________

### Phase 8: AWS EC2 Deployment ⏳

**Status**: ⏳ **NOT STARTED**

#### 8.1 EC2 Instance Setup

- [ ] Launch EC2 instance (t3.medium or t3.large)
- [ ] Configure security group:
  - [ ] SSH (22) from your IP
  - [ ] HTTPS (443) from anywhere
  - [ ] HTTP (8000) from ALB security group only
- [ ] Attach EBS volume (30-50 GB gp3)
- [ ] Assign Elastic IP (optional)

#### 8.2 Server Configuration

- [ ] Install Docker on EC2
- [ ] Install Docker Compose
- [ ] Configure Docker to start on boot
- [ ] Create application directory (`/opt/rag-api`)
- [ ] Clone repository
- [ ] Configure `.env` file with secrets (prefer AWS SSM/Secrets Manager)
- [ ] Copy data and index directories

#### 8.3 HTTPS Configuration

- [ ] Create Application Load Balancer
- [ ] Request ACM certificate for domain
- [ ] Configure HTTPS listener (443)
- [ ] Create target group for EC2:8000
- [ ] Configure health check path (`/health`)
- [ ] Update DNS to point to ALB

#### 8.4 Deployment Script

Create `scripts/deploy.sh`:

- [ ] Pull latest code from repository
- [ ] Build Docker image
- [ ] Stop existing container
- [ ] Start new container
- [ ] Verify health check passes
- [ ] Print deployment status

#### 8.5 Verification

- [ ] HTTPS endpoint accessible
- [ ] Health check returns 200
- [ ] Query endpoint works with authentication
- [ ] Logs accessible via CloudWatch or volume
- [ ] Document deployment steps in README

______________________________________________________________________

### Phase 9: Observability ⏳

**Status**: ⏳ **NOT STARTED**

#### 9.1 Structured Logging

- [ ] Configure uvicorn access logs
- [ ] Add request ID to all log entries
- [ ] Log request method, path, status, latency
- [ ] Log authentication type
- [ ] Log client IP and user agent
- [ ] Redact or hash sensitive identifiers (Slack user/channel IDs)
- [ ] Configure JSON log format for production

#### 9.2 Request Logging Middleware

Create `api/middleware/logging.py`:

- [ ] Generate unique request ID
- [ ] Add request ID to response headers (`X-Request-ID`)
- [ ] Log request start (method, path, client IP)
- [ ] Log request end (status, latency)
- [ ] Include request ID in all logs

#### 9.3 CloudWatch Integration (Optional)

- [ ] Install CloudWatch agent on EC2
- [ ] Configure log streaming to CloudWatch
- [ ] Create log group for API logs
- [ ] Set up log retention policy

#### 9.4 Monitoring Alarms (Optional)

- [ ] Create alarm for `/health` failures
- [ ] Create alarm for high error rate (> 5%)
- [ ] Create alarm for high latency (> 10s)
- [ ] Create alarm for container restarts
- [ ] Configure SNS notifications

#### 9.5 Verification

- [ ] Request ID appears in logs
- [ ] Request ID appears in response headers
- [ ] Logs include all required fields
- [ ] CloudWatch receives logs (if configured)

______________________________________________________________________

### Phase 10: Documentation & Cleanup ⏳

**Status**: ⏳ **NOT STARTED**

#### 10.1 API Documentation

- [ ] Review OpenAPI auto-generated docs
- [ ] Add descriptions to all endpoints
- [ ] Add examples to request/response models
- [ ] Document authentication requirements
- [ ] Document rate limiting behavior
- [ ] Export OpenAPI spec to `docs/openapi.json`

#### 10.2 README Updates

- [ ] Add API section to main README
- [ ] Document local development setup
- [ ] Document Docker deployment
- [ ] Document EC2 deployment
- [ ] Add API usage examples (curl)
- [ ] Link to deployment-specs.md

#### 10.3 Runbook

Create `docs/runbook.md`:

- [ ] Deployment procedures
- [ ] Rollback procedures
- [ ] Common troubleshooting steps
- [ ] Log locations and analysis
- [ ] Emergency contacts

#### 10.4 Testing

- [ ] All API tests passing
- [ ] Integration tests with real RAG backend
- [ ] Load testing (optional)
- [ ] Security review (optional)

#### 10.5 Final Verification

- [ ] Full end-to-end test (Slack → API → RAG → Response)
- [ ] Documentation review
- [ ] Code review
- [ ] Merge to main branch

______________________________________________________________________

## Test Coverage Requirements

| Module                         | Target | Notes                  |
| ------------------------------ | ------ | ---------------------- |
| `api/routes/health.py`         | 90%+   | Simple endpoints       |
| `api/routes/query.py`          | 80%+   | Core functionality     |
| `api/routes/sources.py`        | 80%+   | Simple endpoints       |
| `api/routes/slack.py`          | 70%+   | Integration complexity |
| `api/middleware/auth.py`       | 90%+   | Security critical      |
| `api/middleware/rate_limit.py` | 80%+   | Timing-sensitive       |
| `api/exceptions.py`            | 90%+   | Error handling         |
| `api/models/*.py`              | 90%+   | Validation logic       |

______________________________________________________________________

## Risk Mitigation

| Risk                     | Mitigation                           |
| ------------------------ | ------------------------------------ |
| OpenAI API downtime      | Return 502 with clear error message  |
| Rate limit exhaustion    | Implement backoff, monitor usage     |
| Slack timeout (3s limit) | Async response pattern               |
| Docker image size        | Multi-stage build, slim base image   |
| Secret exposure          | Environment variables, never in code |
| Replay attacks           | Slack timestamp validation (5 min)   |

______________________________________________________________________

## Timeline Estimate

| Phase     | Description             | Estimate    |
| --------- | ----------------------- | ----------- |
| 1         | Project Setup           | 0.5 day     |
| 2         | Core API Implementation | 2 days      |
| 3         | Error Handling          | 0.5 day     |
| 4         | Authentication          | 1 day       |
| 5         | Rate Limiting           | 0.5 day     |
| 6         | Slack Integration       | 1.5 days    |
| 7         | Docker Configuration    | 0.5 day     |
| 8         | AWS EC2 Deployment      | 1 day       |
| 9         | Observability           | 0.5 day     |
| 10        | Documentation & Cleanup | 1 day       |
| **Total** |                         | **~9 days** |

______________________________________________________________________

## Dependencies Between Phases

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Core API) ──────┬──────────────────┐
    │                    │                  │
    ▼                    ▼                  ▼
Phase 3 (Errors)    Phase 4 (Auth)    Phase 5 (Rate Limit)
    │                    │                  │
    └────────────────────┼──────────────────┘
                         │
                         ▼
                   Phase 6 (Slack)
                         │
                         ▼
                   Phase 7 (Docker)
                         │
                         ▼
                   Phase 8 (EC2)
                         │
                         ▼
                   Phase 9 (Observability)
                         │
                         ▼
                   Phase 10 (Docs)
```

______________________________________________________________________

**Document Owner:** Platform Team\
**Review Cycle:** Per Phase Completion
