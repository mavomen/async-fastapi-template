# API Documentation

The API is versioned under `/api/v1`. Full OpenAPI spec is available at `/docs`.

## Authentication

- `POST /api/v1/auth/register` — Create a new user.
- `POST /api/v1/auth/login` — Obtain a JWT token (OAuth2 password flow).

Include the token in requests:

```
Authorization: Bearer <token>
```

## Users (RBAC Protected)

Requires appropriate permissions (`user:read`, `user:write`, `user:delete`).

- `GET /api/v1/users/` — List all users.
- `GET /api/v1/users/{id}` — Get user detail.
- `PATCH /api/v1/users/{id}` — Update user.
- `DELETE /api/v1/users/{id}` — Delete user.

## Files

- `POST /api/v1/files/upload` — Upload a file (multipart).
- `GET /api/v1/files/download/{path}` — Download a file.

## Tasks

- `POST /api/v1/tasks/email/send` — Send an email notification (background).
- `GET /api/v1/tasks/{task_id}` — Check task status.

## Health & Monitoring

- `GET /health` — Basic health.
- `GET /health/ready` — Readiness (DB + Redis).
- `GET /health/live` — Liveness.
- `GET /metrics` — Prometheus metrics.

## WebSocket

- `ws://<host>/ws/chat?token=<jwt>` — Chat WebSocket (authenticated).

## Rate Limiting

Default global limits. Custom limits can be applied with the `@rate_limit` decorator. Headers `X-RateLimit-*` are returned on every response.

## Pagination

Use query parameters `page` and `size` on list endpoints. Response includes `total`, `pages`, `items`.

## Error Handling

Standard HTTP status codes. Validation errors return a 422 with a `detail` message and an `errors` list.
