"""Middleware for caching GET responses globally (or per route)."""

import hashlib
import json

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.cache import cache


class CacheMiddleware(BaseHTTPMiddleware):
    """Cache responses for GET requests with a TTL."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "GET":
            return await call_next(request)

        # Build key
        key = f"mc:{request.url.path}:{request.query_params}"
        key = hashlib.md5(key.encode()).hexdigest()

        cached_data = await cache.get(key)
        if cached_data:
            return Response(
                content=json.dumps(cached_data["body"]),
                status_code=cached_data["status"],
                media_type="application/json",
                headers=cached_data.get("headers", {}),
            )

        response = await call_next(request)

        # Only cache successful JSON responses
        if response.status_code == 200 and "application/json" in response.headers.get(
            "content-type", ""
        ):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            response.body_iterator = _single_body_iterator(body)
            try:
                data = json.loads(body)
                await cache.set(
                    key,
                    {
                        "body": data,
                        "status": response.status_code,
                        "headers": dict(response.headers),
                    },
                    ttl=60,  # default TTL
                )
            except (json.JSONDecodeError, TypeError):
                pass

        return response


async def _single_body_iterator(body: bytes):
    yield body
