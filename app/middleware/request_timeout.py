"""Middleware that aborts requests that exceed a configurable timeout."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Return 408 if the request handler takes longer than ``timeout`` seconds."""

    def __init__(self, app: Any, timeout: int = 30):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout)
        except TimeoutError:
            return PlainTextResponse(
                "Request Timeout",
                status_code=408,
                headers={"Connection": "close"},
            )
