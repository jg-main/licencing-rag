# Docker Deployment Guide

**Version:** 0.4\
**Last Updated:** February 2026

______________________________________________________________________

## Overview

This guide covers deploying the License Intelligence RAG system using Docker and Docker Compose. Docker provides a consistent, isolated environment for both development and production deployments.

______________________________________________________________________

## Prerequisites

- **Docker** 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose** 2.0+ (included with Docker Desktop)
- **OpenAI API Key** ([Get one here](https://platform.openai.com/api-keys))

______________________________________________________________________

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone <repo-url>
cd licencing-rag

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

### 2. Environment Configuration

Edit `.env` and set required variables:

```bash
# Required
OPENAI_API_KEY=sk-your-api-key-here

# API Authentication (if using REST API)
RAG_API_KEY=your-secret-api-key
SLACK_SIGNING_SECRET=your-slack-signing-secret

# Optional
WORKERS=4  # Number of API workers (default: 1 for dev, 4 for production)
```

### 3. Build and Run

```bash
# Build with your user permissions (prevents volume permission issues)
docker-compose build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g)

# Start the service
docker-compose up -d

# Verify it's running
curl http://localhost:8000/health
```

### 4. Load Documents

```bash
# Copy your documents to data/raw/{source}/
mkdir -p data/raw/cme
cp your-documents/*.pdf data/raw/cme/

# Ingest documents (using Docker)
docker-compose exec api rag ingest --source cme

# Or using the API
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the fees?"}'
```

______________________________________________________________________

## Docker Compose Deployment

### Service Configuration

The `docker-compose.yml` defines the API service with:

- **Image**: Built from local Dockerfile
- **Ports**: 8000 exposed for API access
- **Volumes**: Persistent storage for data, indexes, and logs
- **Health Checks**: Automatic health monitoring
- **Restart Policy**: Auto-restart on failure

### Volume Mounts

| Host Path | Container Path | Mode | Purpose                      |
| --------- | -------------- | ---- | ---------------------------- |
| `./data`  | `/app/data`    | ro   | Source documents (read-only) |
| `./index` | `/app/index`   | rw   | ChromaDB and BM25 indexes    |
| `./logs`  | `/app/logs`    | rw   | Query and debug logs         |

**Why read-only for data?**\
The API only reads ingested documents. Making it read-only prevents accidental modifications.

### Common Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Rebuild after code changes
docker-compose build
docker-compose up -d

# Run CLI commands inside container
docker-compose exec api rag query "What are the fees?"
docker-compose exec api rag list --source cme

# Access container shell
docker-compose exec api bash
```

______________________________________________________________________

## Standalone Docker Deployment

For production deployments without Docker Compose:

### Build Image

```bash
# Build with matching user permissions
docker build \
  --build-arg USER_UID=$(id -u) \
  --build-arg USER_GID=$(id -g) \
  -t rag-api:latest .
```

### Run Container

```bash
docker run -d \
  --name rag-api \
  -p 8000:8000 \
  --cpus=2 \
  --memory=4g \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e RAG_API_KEY="$RAG_API_KEY" \
  -e SLACK_SIGNING_SECRET="$SLACK_SIGNING_SECRET" \
  -e WORKERS=4 \
  -v $(pwd)/data:/app/data:ro \
  -v $(pwd)/index:/app/index:rw \
  -v $(pwd)/logs:/app/logs:rw \
  --restart unless-stopped \
  rag-api:latest
```

### Resource Limits

**Development:**

- CPUs: 1-2
- Memory: 2-4 GB

**Production:**

- CPUs: 2-4
- Memory: 4-8 GB

Adjust based on query volume and document size.

______________________________________________________________________

## Configuration

### Environment Variables

| Variable                  | Required | Default | Description                        |
| ------------------------- | -------- | ------- | ---------------------------------- |
| `OPENAI_API_KEY`          | Yes      | —       | OpenAI API key                     |
| `RAG_API_KEY`             | Yes\*    | —       | API key for `/query` endpoint      |
| `SLACK_SIGNING_SECRET`    | Yes\*    | —       | Slack app signing secret           |
| `WORKERS`                 | No       | `1`     | Uvicorn workers (4 for production) |
| `USER_UID`                | No       | `1000`  | Container user UID                 |
| `USER_GID`                | No       | `1000`  | Container group GID                |
| `RAG_LOG_LEVEL`           | No       | `INFO`  | Logging level                      |
| `RAG_CORS_ORIGINS`        | No       | (none)  | Allowed CORS origins               |
| `RAG_RATE_LIMIT`          | No       | `100`   | Requests per minute                |
| `RAG_TRUST_PROXY_HEADERS` | No       | `false` | Trust X-Forwarded-For (behind ALB) |

\* Required when using REST API

### Worker Configuration

The `WORKERS` environment variable controls the number of Uvicorn worker processes:

- **Development**: `WORKERS=1` (single process, easier debugging)
- **Production**: `WORKERS=4` or use formula: `(2 * CPU_CORES) + 1`
  - 2 cores → 5 workers
  - 4 cores → 9 workers

**Note:** Docker Compose sets `WORKERS=4` by default for production workloads.

### Volume Permissions

If you encounter permission errors on mounted volumes:

**Option 1: Build with matching UID/GID (Recommended)**

```bash
docker-compose build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g)
```

**Option 2: Fix host directory permissions**

```bash
sudo chown -R $(id -u):$(id -g) index/ logs/
```

______________________________________________________________________

## Health Checks

The container includes built-in health monitoring:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Check Health Status

```bash
# View health status
docker ps

# Inspect detailed health
docker inspect rag-api | jq '.[0].State.Health'
```

______________________________________________________________________

## Production Deployment

### Recommended Setup

For production deployments:

1. **Use an Application Load Balancer (ALB)** for HTTPS termination
1. **Deploy on AWS EC2, ECS, or similar** with proper resource limits
1. **Configure monitoring** (CloudWatch, Prometheus)
1. **Set up log aggregation** (CloudWatch Logs, ELK stack)
1. **Use secrets management** (AWS Secrets Manager, not environment files)

### Architecture

```
Internet
   ↓
ALB (HTTPS:443)
   ↓
EC2/ECS (HTTP:8000)
   ↓
Docker Container
```

### Security Best Practices

1. **Never expose port 8000 directly to the internet**
1. **Use HTTPS only** (terminate TLS at ALB)
1. **Store secrets in AWS Secrets Manager** or similar
1. **Run container as non-root** (handled automatically)
1. **Keep base image updated** (`python:3.13-slim`)
1. **Enable security scanning** for Docker images

### AWS EC2 Example

```bash
# On EC2 instance
git clone <repo-url> /opt/rag-api
cd /opt/rag-api

# Configure secrets (use AWS Secrets Manager in production)
cat > .env << EOF
OPENAI_API_KEY=sk-...
RAG_API_KEY=your-api-key
SLACK_SIGNING_SECRET=your-secret
EOF

# Build and run
docker-compose build --build-arg USER_UID=1000 --build-arg USER_GID=1000
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

📖 **[Full deployment specs →](development/deployment-specs.md)**

______________________________________________________________________

## Updating and Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild image
docker-compose build

# Restart with new image
docker-compose up -d
```

### Update Documents

```bash
# Add new documents to data/raw/{source}/
cp new-document.pdf data/raw/cme/

# Re-ingest
docker-compose exec api rag ingest --source cme
```

### View Logs

```bash
# Follow API logs
docker-compose logs -f api

# View query logs (inside container)
docker-compose exec api tail -f logs/queries.jsonl

# View debug logs
docker-compose exec api tail -f logs/debug.jsonl
```

### Backup Data

```bash
# Backup indexes and logs
tar -czf backup-$(date +%Y%m%d).tar.gz index/ logs/

# Restore from backup
tar -xzf backup-20260204.tar.gz
```

______________________________________________________________________

## Troubleshooting

### Container Won't Start

**Check logs:**

```bash
docker-compose logs api
```

**Common issues:**

- Missing `OPENAI_API_KEY`
- Port 8000 already in use
- Volume permission errors

### Permission Errors on Volumes

**Symptom:**

```
PermissionError: [Errno 13] Permission denied: '/app/index/chroma'
```

**Solution:**

```bash
# Rebuild with matching UID/GID
docker-compose build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g)
docker-compose up -d
```

### API Returns 503 Service Unavailable

**Cause:** Indexes not loaded yet

**Solution:**

```bash
# Ingest documents first
docker-compose exec api rag ingest --source cme

# Then query
curl http://localhost:8000/query \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the fees?"}'
```

### High Memory Usage

**Check container stats:**

```bash
docker stats rag-api
```

**If memory usage is high:**

1. Reduce `WORKERS` count
1. Increase container memory limit
1. Reduce `TOP_K` in config (fewer chunks retrieved)

### OpenAI API Errors

**Symptom:** 502 errors or "OpenAI API failure"

**Check:**

1. `OPENAI_API_KEY` is valid
1. OpenAI account has credits
1. Not hitting rate limits

**View detailed errors:**

```bash
docker-compose logs api | grep -i openai
```

______________________________________________________________________

## Performance Optimization

### For Better Query Performance

1. **Increase workers**: `WORKERS=4` or higher
1. **Use SSD storage** for index volumes
1. **Allocate more memory**: 4-8 GB for production
1. **Use hybrid search**: Best balance of speed and accuracy

### For Lower Costs

1. **Reduce `TOP_K`**: Retrieve fewer chunks (config in `app/config.py`)
1. **Use vector-only search**: Skip BM25 for faster queries
1. **Monitor OpenAI usage**: Check dashboard regularly

______________________________________________________________________

## Next Steps

- **[Configuration Guide](configuration.md)** - Detailed configuration options
- **[API Documentation](development/deployment-specs.md)** - REST API reference
- **[Cost Estimation](cost-estimation.md)** - Pricing and optimization
- **[Development Guide](development/DEVELOPER_GUIDE.md)** - Contributing to the project

______________________________________________________________________

**Need Help?**

- Check existing [GitHub Issues](https://github.com/your-repo/issues)
- Review [Troubleshooting](#troubleshooting) section
- Open a new issue with logs and configuration
