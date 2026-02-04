# Deployment Specification - License Intelligence API

**Version:** 1.0\
**Last Updated:** February 2026\
**Status:** Draft

______________________________________________________________________

## 1. Overview

This document specifies the deployment of a **FastAPI REST API** layer on top of the existing License Intelligence RAG system. The API enables external clients (e.g., Slack apps) to query licensing documents programmatically.

### Goals

- Expose RAG functionality via REST endpoints
- Enable Slack app integration with secure authentication
- Provide containerized deployment for AWS EC2
- Maintain separation between API layer and RAG core logic

### Non-Goals

- Replicating or duplicating RAG backend logic
- Building a Slack bot (client-side implementation)
- Managing document storage outside of the existing pipeline

______________________________________________________________________

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SLACK WORKSPACE                          │
│  ┌─────────────┐                                                │
│  │  Slack App  │ ─── Slash Commands / Events ───┐               │
│  └─────────────┘                                │               │
└─────────────────────────────────────────────────┼───────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS EC2 INSTANCE                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Docker Container                         │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │                   FastAPI Application                 │  │ │
│  │  │                                                       │  │ │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │  │ │
│  │  │  │  /health    │  │  /query     │  │  /sources    │  │  │ │
│  │  │  └─────────────┘  └──────┬──────┘  └──────────────┘  │  │ │
│  │  │                          │                            │  │ │
│  │  │  ┌───────────────────────▼───────────────────────┐   │  │ │
│  │  │  │              RAG Core Library                  │   │  │ │
│  │  │  │  (app.query, app.ingest, app.search, etc.)     │   │  │ │
│  │  │  └───────────────────────────────────────────────┘   │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                              │                              │ │
│  │  ┌───────────────────────────▼───────────────────────────┐ │ │
│  │  │  Persistent Volumes                                    │ │ │
│  │  │  • /data (documents, chunks)                           │ │ │
│  │  │  • /index (ChromaDB, BM25)                             │ │ │
│  │  │  • /logs (audit, debug)                                │ │ │
│  │  └────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## 3. API Endpoints

### 3.1 Health & Status

| Endpoint   | Method | Auth | Description                      |
| ---------- | ------ | ---- | -------------------------------- |
| `/health`  | GET    | No   | Liveness check                   |
| `/ready`   | GET    | No   | Readiness check (indexes loaded) |
| `/version` | GET    | No   | API and RAG version info         |

**GET /health**

Returns basic liveness status. Use for load balancer health checks.

```json
{
  "status": "healthy",
  "timestamp": "2026-02-02T10:15:30Z"
}
```

**GET /ready**

Verifies the system is ready to serve requests (indexes loaded, configuration present). Avoid live OpenAI calls in readiness checks to prevent flapping and unnecessary cost.

```json
{
  "status": "ready",
  "checks": {
    "chroma_index": true,
    "bm25_index": true,
    "openai_api_key_present": true
  },
  "timestamp": "2026-02-02T10:15:30Z"
}
```

**GET /version**

```json
{
  "api_version": "1.0.0",
  "rag_version": "0.4",
  "models": {
    "embeddings": "text-embedding-3-large",
    "llm": "gpt-4.1"
  }
}
```

______________________________________________________________________

### 3.2 Query Endpoints

| Endpoint | Method | Auth | Description              |
| -------- | ------ | ---- | ------------------------ |
| `/query` | POST   | Yes  | Query the knowledge base |

**POST /query**

Primary endpoint for asking questions about licensing documents.

**Request:**

```json
{
  "question": "What are the CME redistribution fees?",
  "sources": ["cme"],
  "options": {
    "search_mode": "hybrid",
    "top_k": 10,
    "enable_reranking": true,
    "enable_confidence_gate": true,
    "include_definitions": false
  }
}
```

| Field                            | Type     | Required | Default    | Description                      |
| -------------------------------- | -------- | -------- | ---------- | -------------------------------- |
| `question`                       | string   | Yes      | —          | The question to ask              |
| `sources`                        | string[] | No       | all        | Filter by data sources           |
| `options.search_mode`            | string   | No       | `"hybrid"` | `vector`, `keyword`, or `hybrid` |
| `options.top_k`                  | integer  | No       | 10         | Number of chunks to retrieve     |
| `options.enable_reranking`       | boolean  | No       | true       | Enable LLM reranking             |
| `options.enable_confidence_gate` | boolean  | No       | true       | Enable confidence gating         |
| `options.include_definitions`    | boolean  | No       | false      | Include auto-linked definitions  |

**Response (Success):**

```json
{
  "success": true,
  "data": {
    "answer": "The CME redistribution fees are...",
    "citations": [
      {
        "source": "cme",
        "document": "january-2026-market-data-fee-list.pdf",
        "section": "Schedule A",
        "page": 3
      }
    ],
    "definitions": [],
    "metadata": {
      "query_id": "uuid-here",
      "sources_queried": ["cme"],
      "chunks_retrieved": 12,
      "chunks_used": 3,
      "tokens_input": 4523,
      "tokens_output": 234,
      "latency_ms": 3421,
      "refused": false
    }
  }
}
```

**Response (Refused - Low Confidence):**

```json
{
  "success": true,
  "data": {
    "answer": "This is not addressed in the provided CME documents.",
    "citations": [],
    "metadata": {
      "query_id": "uuid-here",
      "refused": true,
      "refusal_reason": "confidence_below_threshold"
    }
  }
}
```

______________________________________________________________________

### 3.3 Document Management

| Endpoint          | Method | Auth | Description               |
| ----------------- | ------ | ---- | ------------------------- |
| `/sources`        | GET    | Yes  | List available sources    |
| `/sources/{name}` | GET    | Yes  | List documents for source |

**GET /sources**

```json
{
  "sources": [
    {
      "name": "cme",
      "display_name": "CME Group",
      "document_count": 44,
      "status": "active"
    },
    {
      "name": "opra",
      "display_name": "OPRA",
      "document_count": 0,
      "status": "planned"
    }
  ]
}
```

**GET /sources/{name}**

```json
{
  "source": "cme",
  "documents": [
    "fees/january-2026-market-data-fee-list.pdf",
    "legal/schedule-2-to-the-ila.pdf"
  ],
  "total_count": 44
}
```

______________________________________________________________________

### 3.4 Slack Endpoints

| Endpoint         | Method | Auth  | Description               |
| ---------------- | ------ | ----- | ------------------------- |
| `/slack/command` | POST   | Slack | Slash command integration |

______________________________________________________________________

## 4. Authentication

### 4.1 Strategy: API Key + Slack Signature Verification

The API uses a **dual authentication** approach suitable for Slack integration:

1. **API Key** — For direct API access and testing
1. **Slack Request Signing** — For requests originating from Slack

**Endpoint coverage:**

- `/query`, `/sources`, `/sources/{name}` require API key authentication.
- `/slack/command` requires Slack signature verification only.
- Health endpoints (`/health`, `/ready`, `/version`) are public.

### 4.2 API Key Authentication

For non-Slack clients (testing, internal tools):

```http
Authorization: Bearer <API_KEY>
```

**Configuration:**

```bash
# Environment variable
RAG_API_KEY="your-secret-api-key-here"
```

### 4.3 Slack Request Verification

For Slack app requests, verify the `X-Slack-Signature` header using your Slack signing secret:

```python
import hmac
import hashlib
import time

def verify_slack_request(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Verify request originated from Slack."""
    # Reject requests older than 5 minutes (replay protection)
    if abs(time.time() - int(timestamp)) > 300:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

**Required Headers from Slack:**

- `X-Slack-Signature` — HMAC signature
- `X-Slack-Request-Timestamp` — Unix timestamp

**Configuration:**

```bash
SLACK_SIGNING_SECRET="your-slack-signing-secret"
```

### 4.4 Authentication Flow

```
Request Received
       │
       ▼
┌────────────────────────────┐
│ Is /slack/command endpoint? │
└───────────────┬────────────┘
                │
         ┌──────┴──────┐
         │             │
        Yes           No
         │             │
         ▼             ▼
┌────────────────┐  ┌─────────────────┐
│ Verify Slack   │  │ Check Bearer    │
│ Signature      │  │ Token (API Key) │
└───────┬────────┘  └────────┬────────┘
        │                    │
        ▼                    ▼
     Valid?               Valid?
        │                    │
     ┌──┴──┐              ┌──┴──┐
     │     │              │     │
    Yes    No            Yes    No
     │     │              │     │
     ▼     ▼              ▼     ▼
    OK    401            OK    401
```

______________________________________________________________________

## 5. Error Handling

### 5.1 Error Response Format

All errors follow a consistent structure:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Question is required",
    "details": {
      "field": "question",
      "reason": "Field cannot be empty"
    }
  },
  "request_id": "uuid-here"
}
```

### 5.2 Error Codes

| HTTP | Code                  | Description                           |
| ---- | --------------------- | ------------------------------------- |
| 400  | `VALIDATION_ERROR`    | Invalid or missing request fields     |
| 400  | `EMPTY_QUESTION`      | Question field is empty               |
| 401  | `UNAUTHORIZED`        | Missing or invalid authentication     |
| 403  | `FORBIDDEN`           | Valid auth but insufficient access    |
| 404  | `SOURCE_NOT_FOUND`    | Requested source doesn't exist        |
| 422  | `UNPROCESSABLE`       | Request valid but cannot be processed |
| 429  | `RATE_LIMITED`        | Too many requests                     |
| 500  | `INTERNAL_ERROR`      | Unexpected server error               |
| 502  | `OPENAI_ERROR`        | OpenAI API failure                    |
| 503  | `SERVICE_UNAVAILABLE` | System not ready (index loading)      |

### 5.3 Request Validation

The API validates all incoming requests:

**Empty/Invalid Requests:**

```json
// Request
POST /query
{}

// Response (400)
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request body is required"
  }
}
```

**Empty Question:**

```json
// Request
{"question": "   "}

// Response (400)
{
  "success": false,
  "error": {
    "code": "EMPTY_QUESTION",
    "message": "Question cannot be empty or whitespace only"
  }
}
```

**Invalid Source:**

```json
// Request
{"question": "What are the fees?", "sources": ["invalid"]}

// Response (404)
{
  "success": false,
  "error": {
    "code": "SOURCE_NOT_FOUND",
    "message": "Source 'invalid' not found",
    "details": {
      "available_sources": ["cme", "opra", "cta-utp"]
    }
  }
}
```

______________________________________________________________________

## 6. Rate Limiting

For multi-worker or multi-instance deployments, use a shared store (e.g., Redis) or an upstream rate limiter (ALB/WAF) to ensure consistent enforcement.

### 6.1 Limits

| Scope       | Limit         | Window   |
| ----------- | ------------- | -------- |
| Per API Key | 100 requests  | 1 minute |
| Per IP      | 20 requests   | 1 minute |
| Burst       | 10 concurrent | —        |

### 6.2 Response Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1706875200
```

### 6.3 Rate Limit Exceeded

```json
// Response (429)
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again in 45 seconds.",
    "details": {
      "retry_after": 45
    }
  }
}
```

______________________________________________________________________

## 7. Docker Configuration

### 7.1 Dockerfile

**Production-Grade Features:**

- Multi-stage build for reduced image size
- Pinned `uv` version (0.5.18) via pip for supply-chain hardening
- Uses `uv export --frozen` + `uv pip install` for fully lockfile-pinned builds
- Configurable UID/GID with safe creation logic (checks username, then UID/GID availability, fails on conflicts)
- Configurable workers via `WORKERS` env var (default: 1, Compose override: 4)
- Non-root user execution
- Health check integration
- Proper signal handling (exec form with PID 1)

**Key Configuration:**

```dockerfile
FROM python:3.13-slim AS builder
# Install pinned uv version
RUN pip install --no-cache-dir uv==0.5.18
COPY pyproject.toml uv.lock ./
# Export locked deps (--no-emit-project excludes local package) and install to system
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o requirements.txt && \
    uv pip install --system --no-cache -r requirements.txt

FROM python:3.13-slim
# Configurable UID/GID for volume permissions
# Logic: check username first, then verify UID/GID availability, fail on conflicts
ARG USER_UID=1000
ARG USER_GID=1000
RUN set -e && \
    # Handle group: use existing or create with requested GID if available
    if getent group appuser >/dev/null; then echo "Group exists"; \
    elif getent group ${USER_GID} >/dev/null; then echo "ERROR: GID in use" && exit 1; \
    else groupadd -g ${USER_GID} appuser; fi && \
    # Handle user: use existing or create with requested UID if available
    if id appuser >/dev/null 2>&1; then echo "User exists"; \
    elif getent passwd ${USER_UID} >/dev/null; then echo "ERROR: UID in use" && exit 1; \
    else useradd -u ${USER_UID} -g appuser --create-home appuser; fi

# Configurable workers (default: 1, Compose sets 4 for production)
ENV WORKERS=1
# Signal-safe startup with exec (uvicorn becomes PID 1)
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS}"]
```

### 7.2 Docker Compose (Development)

**Important Notes:**

- `deploy.resources` are NOT enforced in Docker Compose standalone mode (only in Swarm)
- For actual resource limits, use Docker CLI flags (`--cpus`, `--memory`) or deploy to Kubernetes/Swarm
- Build with matching UID/GID to avoid volume permission issues

```yaml
version: "3.9"

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        USER_UID: ${USER_UID:-1000}
        USER_GID: ${USER_GID:-1000}
    image: rag-api:latest
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - RAG_API_KEY=${RAG_API_KEY}
      - SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}
      - WORKERS=${WORKERS:-4}  # Production: 4 workers
    volumes:
      - ./data:/app/data:ro
      - ./index:/app/index:rw
      - ./logs:/app/logs:rw
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 7.3 Build and Run

**Production Deployment Considerations**:

1. **Workers**: Set `WORKERS=4` (or `(2 * CPU_CORES) + 1`) for production load handling
1. **Volume Permissions**: Build with matching UID/GID to avoid permission errors on bind mounts
1. **Resource Limits**: `deploy.resources` in Compose are NOT enforced in standalone mode. For actual enforcement use Docker CLI `--cpus` / `--memory` flags, cgroup limits, or deploy to Kubernetes/Swarm
1. **Dependency Updates**: Run `uv lock` after updating pyproject.toml, then rebuild image for reproducibility
1. **Supply Chain Security**: uv pinned to version 0.5.18 via pip (not shell script) for verifiable builds

**Development:**

```bash
# Build with host user permissions (avoids volume permission errors)
docker-compose build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g)

# Run with docker-compose (4 workers for production load)
WORKERS=4 docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down
```

**Production (standalone):**

```bash
# Build image
docker build \
  --build-arg USER_UID=$(id -u) \
  --build-arg USER_GID=$(id -g) \
  -t rag-api:latest .

# Run container with resource limits (enforced in standalone mode)
docker run -d \
  --name rag-api \
  -p 8000:8000 \
  --cpus=2 \
  --memory=4g \
  -e WORKERS=4 \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e RAG_API_KEY="$RAG_API_KEY" \
  -e SLACK_SIGNING_SECRET="$SLACK_SIGNING_SECRET" \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/index:/app/index:rw \
  -v $(pwd)/logs:/app/logs:rw \
  --restart unless-stopped \
  rag-api:latest
```

**Worker Configuration:**

- **Development**: `WORKERS=1` (default, single process)
- **Production**: `WORKERS=4` or `(2 * CPU_CORES) + 1`
- Example: 2 CPU cores → `WORKERS=5`

**Volume Permissions:**

If you encounter permission errors on `/app/index` or `/app/logs`:

1. Build with matching UID/GID: `--build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g)`
1. Or fix host directory permissions: `sudo chown -R $(id -u):$(id -g) index/ logs/`

______________________________________________________________________

## 8. AWS EC2 Deployment

### 8.1 Instance Requirements

| Component     | Minimum         | Recommended     |
| ------------- | --------------- | --------------- |
| Instance Type | t3.medium       | t3.large        |
| vCPUs         | 2               | 4               |
| Memory        | 4 GB            | 8 GB            |
| Storage       | 30 GB EBS (gp3) | 50 GB EBS (gp3) |
| Network       | Moderate        | High            |

### 8.2 Security Group Rules

**Inbound:**

| Port | Protocol | Source      | Description                   |
| ---- | -------- | ----------- | ----------------------------- |
| 22   | TCP      | Your IP     | SSH access                    |
| 443  | TCP      | 0.0.0.0/0   | HTTPS (via ALB)               |
| 8000 | TCP      | ALB SG only | API (internal, from ALB only) |

**Outbound:**

| Port | Protocol | Destination | Description |
| ---- | -------- | ----------- | ----------- |
| 443  | TCP      | 0.0.0.0/0   | OpenAI API  |

### 8.3 Deployment Steps

```bash
# 1. Connect to EC2
ssh -i your-key.pem ec2-user@your-instance-ip

# 2. Install Docker
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# 3. Clone repository
git clone <your-repo-url> /opt/rag-api
cd /opt/rag-api

# 4. Configure environment
# Prefer a secrets manager (AWS SSM/Secrets Manager) in production.
cat > .env << EOF
OPENAI_API_KEY=sk-...
RAG_API_KEY=your-api-key
SLACK_SIGNING_SECRET=your-signing-secret
EOF

# 5. Build and run
docker compose up -d

# 6. Verify deployment
curl http://localhost:8000/health
```

### 8.4 HTTPS with Application Load Balancer

For production, terminate TLS at an Application Load Balancer:

1. Create an ALB in your VPC
1. Add HTTPS listener (port 443) with ACM certificate
1. Create target group pointing to EC2:8000
1. Configure health check path: `/health`

```
Internet → ALB (HTTPS:443) → EC2 (HTTP:8000) → Docker Container
```

______________________________________________________________________

## 9. Environment Variables

| Variable                  | Required | Default | Description                        |
| ------------------------- | -------- | ------- | ---------------------------------- |
| `OPENAI_API_KEY`          | Yes      | —       | OpenAI API key                     |
| `RAG_API_KEY`             | Yes      | —       | API authentication key             |
| `SLACK_SIGNING_SECRET`    | Yes\*    | —       | Slack app signing secret           |
| `RAG_LOG_LEVEL`           | No       | `INFO`  | Logging level                      |
| `RAG_CORS_ORIGINS`        | No       | (none)  | Allowed CORS origins               |
| `RAG_RATE_LIMIT`          | No       | `100`   | Requests per minute per key        |
| `RAG_TRUST_PROXY_HEADERS` | No       | `false` | Trust X-Forwarded-For (behind ALB) |

\*Required if accepting Slack requests

______________________________________________________________________

## 10. Observability

### 10.1 Logging

All requests are logged in structured JSON format. Avoid logging Slack payloads or other sensitive data; redact or hash user identifiers where possible.

```json
{
  "timestamp": "2026-02-02T10:15:30Z",
  "level": "INFO",
  "request_id": "uuid",
  "method": "POST",
  "path": "/query",
  "status": 200,
  "latency_ms": 3421,
  "client_ip": "1.2.3.4",
  "user_agent": "Slack-Bot"
}
```

### 10.2 Metrics (Future)

Consider exposing Prometheus metrics at `/metrics`:

- `rag_requests_total` — Counter by endpoint and status
- `rag_request_duration_seconds` — Histogram of latencies
- `rag_tokens_used_total` — Counter of OpenAI tokens consumed

### 10.3 Health Monitoring

Configure CloudWatch alarms for:

- `/health` endpoint failures
- Response latency > 10 seconds
- Error rate > 5%
- Container restarts

______________________________________________________________________

## 11. Slack Integration Guide

### 11.1 Slack App Setup

1. Create a new Slack app at [api.slack.com](https://api.slack.com)
1. Enable **Slash Commands** feature
1. Create a command (e.g., `/ask-license`)
1. Set Request URL to `https://your-domain.com/slack/command`
1. Copy the **Signing Secret** to your environment

### 11.2 Slash Command Endpoint

The API should include a dedicated Slack endpoint. This endpoint uses Slack signature verification (no API key required).

**POST /slack/command**

Handles Slack slash command payloads:

```
token=xxx&team_id=T0001&channel_id=C2147483705
&user_id=U2147483697&command=/ask-license
&text=What are the CME redistribution fees?
&response_url=https://hooks.slack.com/commands/...
```

**Response (immediate acknowledgment):**

```json
{
  "response_type": "ephemeral",
  "text": "🔍 Searching licensing documents..."
}
```

Then send the actual answer via `response_url` (async).

### 11.3 Response Formatting

Format responses for Slack using Block Kit:

```json
{
  "response_type": "in_channel",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Answer:*\nThe CME redistribution fees are..."
      }
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": "📄 Source: january-2026-market-data-fee-list.pdf | Page 3"
        }
      ]
    }
  ]
}
```

______________________________________________________________________

## 12. Implementation Checklist

### Phase 1: Core API

- [ ] Create `api/` directory structure
- [ ] Implement FastAPI application (`api/main.py`)
- [ ] Add `/health`, `/ready`, `/version` endpoints
- [ ] Add `/query` endpoint (wraps `app.query.query()`)
- [ ] Add `/sources` endpoints
- [ ] Implement request validation with Pydantic models
- [ ] Add comprehensive error handling

### Phase 2: Authentication

- [ ] Implement API key middleware
- [ ] Implement Slack signature verification
- [ ] Add authentication dependency injection
- [ ] Create API key management utilities

### Phase 3: Docker & Deployment

- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Test local Docker deployment
- [ ] Document EC2 deployment steps
- [ ] Configure ALB and TLS

### Phase 4: Slack Integration

- [ ] Add `/slack/command` endpoint
- [ ] Implement async response via `response_url`
- [ ] Format responses with Block Kit
- [ ] Test end-to-end Slack flow

### Phase 5: Production Hardening

- [ ] Add rate limiting
- [ ] Configure structured logging
- [ ] Set up CloudWatch monitoring
- [ ] Perform load testing
- [ ] Document runbook

______________________________________________________________________

## 13. Security Considerations

1. **API Keys** — Store securely (AWS Secrets Manager, environment variables)
1. **TLS** — Always use HTTPS in production (terminate at ALB)
1. **Least Privilege** — Run container as non-root user
1. **Input Validation** — Validate and sanitize all inputs
1. **Rate Limiting** — Prevent abuse and DoS
1. **Secrets Rotation** — Plan for periodic API key rotation
1. **Audit Logging** — Log all requests for compliance

______________________________________________________________________

## 14. Cost Estimation

### EC2 + OpenAI Costs

| Component           | Monthly Cost (Est.) |
| ------------------- | ------------------- |
| t3.medium EC2       | ~$30                |
| 50 GB EBS           | ~$5                 |
| ALB                 | ~$20                |
| OpenAI (3k queries) | ~$90                |
| **Total**           | **~$145/month**     |

______________________________________________________________________

**Document Owner:** Platform Team\
**Review Cycle:** Quarterly
