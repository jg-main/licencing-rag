# api/models/__init__.py
"""Pydantic models for API request/response schemas.

Contains data models for:
- Request validation (QueryRequest, QueryOptions)
- Response serialization (QueryResponse, ErrorResponse)
- Health check responses
"""

from api.models.requests import QueryOptions
from api.models.requests import QueryRequest
from api.models.responses import Citation
from api.models.responses import Definition
from api.models.responses import ErrorDetails
from api.models.responses import ErrorInfo
from api.models.responses import ErrorResponse
from api.models.responses import HealthResponse
from api.models.responses import ModelsInfo
from api.models.responses import QueryData
from api.models.responses import QueryMetadata
from api.models.responses import QueryResponse
from api.models.responses import ReadyChecks
from api.models.responses import ReadyResponse
from api.models.responses import SourceDocumentsResponse
from api.models.responses import SourceInfo
from api.models.responses import SourcesResponse
from api.models.responses import VersionResponse

__all__ = [
    # Requests
    "QueryOptions",
    "QueryRequest",
    # Health responses
    "HealthResponse",
    "ReadyChecks",
    "ReadyResponse",
    "ModelsInfo",
    "VersionResponse",
    # Query responses
    "Citation",
    "Definition",
    "QueryMetadata",
    "QueryData",
    "QueryResponse",
    # Sources responses
    "SourceInfo",
    "SourcesResponse",
    "SourceDocumentsResponse",
    # Error responses
    "ErrorDetails",
    "ErrorInfo",
    "ErrorResponse",
]
