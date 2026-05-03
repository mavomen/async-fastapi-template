"""Middleware that logs errors during request processing."""

import logging
import time

from fastapi import Request

logger = logging.getLogger("app.error")


async def error_logging_middleware(request: Request, call_next):
    """Log all requests and capture any unhandled exceptions."""
    start_time = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration = time.monotonic() - start_time
        logger.exception(
            "Unhandled exception",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        raise
    else:
        duration = time.monotonic() - start_time
        logger.info(
            "Request processed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return response
