"""Middleware that counts SQL queries per request and exposes a Prometheus histogram."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import query_count_var
from app.core.metrics import http_queries_per_request


class QueryCountMiddleware(BaseHTTPMiddleware):
    """Count database queries executed during the request lifecycle."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        query_count_var.set(0)
        response = await call_next(request)
        count = query_count_var.get()
        http_queries_per_request.observe(count)
        response.headers["X-Query-Count"] = str(count)
        return response
