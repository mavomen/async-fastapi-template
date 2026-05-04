# API Documentation

The API is versioned under `/api/v1`. The full interactive OpenAPI specification is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

## Versioning

The current version is `v1`. Breaking changes will be introduced under a new version prefix (e.g., `/api/v2`). Non‑breaking additions may be added to the current version.

## Authentication

All protected endpoints require a JWT token passed in the `Authorization` header as `Bearer <token>`.

### Register

**`POST /api/v1/auth/register`**

Create a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Responses:**

- `201` – User created. Returns public user data.
- `400` – Email or username already exists.
- `422` – Validation error.

### Login

**`POST /api/v1/auth/login`**

Obtain a JWT access token. Use `application/x-www-form-urlencoded` format.

**Form Fields:**

- `username` (email)
- `password`

**Responses:**

- `200` – Access token returned.
- `401` – Incorrect credentials.

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=user@example.com" \
  -d "password=SecurePassword123!"
```

**Example Response:**

```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

## Users (RBAC Protected)

All user management endpoints require appropriate permissions (`user:read`, `user:write`, `user:delete`).

### List Users

**`GET /api/v1/users/`**

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

- `page` (int, default 1)
- `size` (int, default 50, max 100)

**Response:** Paginated list of users with their roles.

### Get User

**`GET /api/v1/users/{user_id}`**

**Response:** Single user detail including roles.

### Update User

**`PATCH /api/v1/users/{user_id}`**

**Request Body:** Any subset of `UserUpdate` fields.

### Delete User

**`DELETE /api/v1/users/{user_id}`**

## Files

### Upload a File

**`POST /api/v1/files/upload`**

**Headers:** `Authorization: Bearer <token>`

**Request:** Multipart form with `file` field.

**Response:**

```json
{
  "filename": "document.pdf",
  "path": "document.pdf"
}
```

### Download a File

**`GET /api/v1/files/download/{path}`**

Returns the file content with `application/octet-stream`.

## Background Tasks

### Send Email Notification

**`POST /api/v1/tasks/email/send`**

**Request Body:**

```json
{
  "recipient": "user@example.com",
  "subject": "Welcome!",
  "body": "Thank you for signing up."
}
```

**Response:**

```json
{
  "task_id": "abc123...",
  "status": "PENDING"
}
```

### Get Task Status

**`GET /api/v1/tasks/{task_id}`**

**Response:**

```json
{
  "task_id": "abc123...",
  "status": "SUCCESS",
  "error": null,
  "completed_at": "2026-05-04T12:00:00Z"
}
```

## Health & Monitoring

### Basic Health

**`GET /health`** – Returns `{"status": "healthy"}`.

### Readiness Probe

**`GET /health/ready`** – Checks database and Redis connectivity.

### Liveness Probe

**`GET /health/live`** – Minimal alive check.

### Prometheus Metrics

**`GET /metrics`** – Exposes metrics in Prometheus text format.

## Rate Limiting

Default global limits are applied. Headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` are returned on every response. When exceeded, `429 Too Many Requests` is returned.

## Pagination

List endpoints accept `page` and `size` query parameters. Responses include:

```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "size": 50,
  "pages": 2
}
```

## Error Handling

Standard HTTP status codes are used. Validation errors return a `422` with:

```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "email",
      "message": "value is not a valid email address",
      "type": "value_error"
    }
  ]
}
```
