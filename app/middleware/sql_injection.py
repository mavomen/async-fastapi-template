"""Middleware to log potential SQL injection attempts."""

import re

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger("app.security")

SQL_PATTERNS = [
    r"(\%27)|(\')|(\-\-)|(\%23)|(#)",
    r"((\%3D)|(=))[^\n]*((\%27)|(\')|(\-\-)|(\%3B)|(;))",
    r"w*((\%27)|(\'))\s*((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
    r"((\%27)|(\'))\s*union",
]


class SQLInjectionMonitorMiddleware(BaseHTTPMiddleware):
    """Log requests containing suspicious SQL patterns."""

    async def dispatch(self, request: Request, call_next):
        query_str = str(request.url)
        for pattern in SQL_PATTERNS:
            if re.search(pattern, query_str, re.IGNORECASE):
                logger.warning(
                    "Potential SQL injection detected",
                    pattern=pattern,
                    url=str(request.url),
                    client=request.client.host if request.client else "unknown",
                )
                break
        return await call_next(request)
