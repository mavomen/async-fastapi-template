"""API versioning middleware — content negotiation via Accept header."""

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

_VERSION_PATTERN = re.compile(r"application/vnd\.app\.v(\d+)\+json")


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Extract API version from Accept header and inject response headers.

    Version negotiation:
    - ``Accept: application/vnd.app.v2+json`` → version 2
    - No Accept header or plain JSON → version from URL prefix (default v1)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        version = self._extract_version(request)
        request.state.api_version = version

        response = await call_next(request)
        response.headers["X-API-Version"] = str(version)

        # Deprecation headers for old versions
        if settings.API_DEPRECATED_SINCE and version < int(settings.API_DEPRECATED_SINCE):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = settings.API_DEPRECATED_SUNSET_DATE

        return response

    def _extract_version(self, request: Request) -> int:
        accept = request.headers.get("accept", "")
        match = _VERSION_PATTERN.search(accept)
        if match:
            return int(match.group(1))
        # Fall back to URL prefix
        path = request.url.path
        url_match = re.search(r"/api/v(\d+)", path)
        if url_match:
            return int(url_match.group(1))
        return 1
