# api/routes/__init__.py
"""API route modules.

Contains endpoint definitions for:
- Health checks (/health, /ready, /version)
- Query operations (/query)
- Source management (/sources)
- Slack integration (/slack) [Phase 6 - not yet implemented]
"""

from api.routes.health import router as health_router
from api.routes.query import router as query_router
from api.routes.sources import router as sources_router

__all__ = ["health_router", "query_router", "sources_router"]
