# Caching Strategy Guide

The project uses **Redis** as a cache backend, with an async client wrapper, a decorator for endpoints, and invalidation utilities.

## Setup

- Redis must be running. Configure `REDIS_URL` in environment variables.
- The global cache instance is initialized in `app/core/cache.py`.

## Cache Decorator

Decorate any endpoint to cache its response:

```python
from app.decorators.cache import cached

@router.get("/items")
@cached(ttl=120, key_prefix="items")
async def get_items(request: Request):
  return [{"id": 1, "name": "Item"}]
```

- ttl: seconds to keep the response.

- key_prefix: optional string to group keys.

The decorator uses the full URL path and query parameters to build a unique key.

## Cache Invalidation

Manually invalidate keys matching a prefix:

```python
from app.utils.cache_invalidation import invalidate_by_prefix

await invalidate_by_prefix("items")
```

## Middleware Caching (Optional)

A global middleware can cache GET responses automatically. Enable it in main.py by adding:

```python
from app.middleware.cache_middleware import CacheMiddleware
app.add_middleware(CacheMiddleware)
```

Use with care – only suitable for idempotent, rarely‑changing endpoints.

## Redis Connection

The cache client uses redis.asyncio with hiredis for speed. It’s initialized during app startup via the lifespan handler (example):

```python
from app.core.cache import cache

@asynccontextmanager
async def lifespan(app: FastAPI):
  await cache.connect()
  yield
  await cache.disconnect()
```

Currently, the lifespan does not auto‑connect; you can add that if you want the cache available globally.
