# Rate Limiting Guide

This project uses **slowapi** to enforce rate limits on API endpoints.

## Configuration

Environment variables (in `app/core/config.py`):

- `RATE_LIMIT_PER_MINUTE` (default 60)
- `RATE_LIMIT_PER_HOUR` (default 1000)
- `RATE_LIMIT_PER_DAY` (default 10000)

These apply globally as default limits. The limiter uses the client IP address as the key.

## Per‑route Limits

Use the `@rate_limit` decorator on any endpoint:

```python
from app.decorators.rate_limit import rate_limit

@router.get("/expensive")
@rate_limit(times=5, seconds=30)
async def expensive():
    ...
```

## Response Headers

Every response includes rate‑limit headers:

- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset

When exceeded, the API returns 429 Too Many Requests with a Retry-After header.

## Middleware

The rate limiter is configured in app/middleware/rate_limit.py and attached to the app in main.py. No additional middleware setup is required.
