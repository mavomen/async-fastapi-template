# Rate Limiting Guide

This project uses a **Redis sliding-window** rate limiter with four tiers.
The implementation lives in `app/middleware/redis_rate_limit.py` and is wired
into the app automatically — no additional setup is required.

## Tiers

| Tier | Limit | Applies to |
|------|-------|------------|
| `sensitive` | 5 req/min | Auth endpoints (login, register, OAuth, TOTP, magic-link) |
| `authenticated` | 100 req/min | Any request from a logged-in user (non-sensitive, non-admin) |
| `public` | 20 req/min | All other requests |
| `admin` | 300 req/min | `/admin/*` routes |

The window is 60 seconds by default (`RATE_LIMIT_WINDOW_SECONDS`).

## Configuration

Environment variables (in `app/core/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Master on/off switch |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window duration |
| `RATE_LIMIT_SENSITIVE` | `5` | Max requests per window for sensitive endpoints |
| `RATE_LIMIT_PUBLIC` | `20` | Max requests per window for unauthenticated endpoints |
| `RATE_LIMIT_AUTHENTICATED` | `100` | Max requests per window for authenticated endpoints |
| `RATE_LIMIT_ADMIN` | `300` | Max requests per window for admin endpoints |

## Per-route Limits

Use the `@rate_limit` decorator on any endpoint for a custom limit
that overrides the tier default:

```python
from app.decorators.rate_limit import rate_limit

@router.get("/expensive")
@rate_limit(times=5, seconds=30)
async def expensive():
    ...
```

## Response Headers

Every successful response includes:

- `X-RateLimit-Limit` — max requests in the current window
- `X-RateLimit-Remaining` — requests left in the current window
- `X-RateLimit-Reset` — Unix timestamp when the window resets

When exceeded, the API returns `429 Too Many Requests` with a
`Retry-After` header and an `error_code: "RATE_LIMITED"` body.

## Identifier

The rate limit key is derived from:

1. **Authenticated users**: `user_id` from the JWT payload
2. **Anonymous users**: client IP address (respects `X-Forwarded-For`)

## Prometheus Metrics

- `rate_limit_blocked_total` — counter of 429 responses, labeled by `tier` and `endpoint`
- `rate_limit_remaining` — gauge of remaining requests, labeled by `tier`
