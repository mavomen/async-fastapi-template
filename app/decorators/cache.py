"""Decorator for caching FastAPI endpoint responses."""

import functools
import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response

from app.core.cache import cache


def cached(ttl: int = 60, key_prefix: str = "") -> Callable[..., Any]:
    """Decorator to cache endpoint response in Redis.

    Args:
        ttl: Cache time-to-live in seconds.
        key_prefix: Optional prefix for cache key.

    Returns:
        Decorated function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key from URL path and query params (using request if available)
            request: Request | None = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                # Try to find request in kwargs
                request = kwargs.get("request")
            if not request:
                # Fallback: call original without caching
                return await func(*args, **kwargs)

            cache_key = _build_cache_key(key_prefix, request)

            # Try to get from cache
            cached_response = await cache.get(cache_key)
            if cached_response:
                # Return a Response with same status code and body
                return Response(
                    content=json.dumps(cached_response["body"]),
                    status_code=cached_response["status"],
                    media_type="application/json",
                )

            # Call original endpoint
            response = await func(*args, **kwargs)

            # Store in cache if status is 200
            if isinstance(response, dict) or isinstance(response, list):
                await cache.set(
                    cache_key,
                    {"status": 200, "body": response},
                    ttl=ttl,
                )
            elif isinstance(response, Response) and response.status_code == 200:
                # We could extract body, but for simplicity cache only dict/list responses
                pass

            return response

        return wrapper

    return decorator


def _build_cache_key(prefix: str, request: Request) -> str:
    """Construct a deterministic cache key from request path and query params."""
    raw = f"{prefix}:{request.url.path}:{request.query_params}"
    return hashlib.md5(raw.encode()).hexdigest()
