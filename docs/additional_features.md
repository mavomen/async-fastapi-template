# Additional Features Guide

## Email Service

The project includes a structured `EmailService` that renders Jinja2 templates and logs emails. To integrate a real SMTP server, replace the `send_email` method with a library like `aiosmtplib`.

### Email Verification

- Use `POST /api/v1/auth/verify-request` (authenticated) to send a verification email.
- The user clicks the link which calls `GET /api/v1/auth/verify-email?token=...` to verify.

Templates are stored in `app/templates/email/`.

## Data Export

### CSV/Excel Export

Users can be exported to CSV or Excel via:

```
GET /api/v1/users/export?format=csv
GET /api/v1/users/export?format=excel
```

Requires `user:read` permission.

Utilities `export_to_csv` and `export_to_excel` can be reused for any data.

## Adding Custom Features

Use these examples as a starting point for your own business logic.

## Cache Warming & Cache‑Aside

Utilities in `app/utils/cache_warming.py`:

- `cache_aside(key, fetch_func, ttl)` – returns cached value or fetches and stores.
- `warm_cache(keys_and_fetchers, ttl)` – batch‑warms multiple keys.

Use these at app startup or when data changes to pre‑populate the cache.

## Email Retry with Exponential Backoff

The `EmailService` now exposes a Celery task `send_email_with_retry` that retries up to 5 times with exponential backoff (2ⁿ × 60s). Use it for reliable email delivery.

## Streaming File Upload with Progress

`POST /api/v1/files/upload/stream` accepts a file and returns Server‑Sent Events (`start`, `progress`, `complete`) showing upload progress. Useful for large files.

## Bulk User Import from CSV

`POST /api/v1/users/import/csv` accepts a CSV file and creates users. Requires `user:write` permission. The CSV must have `email` and `username` columns; `password` and `full_name` are optional.

## Server‑Sent Events for Task Progress

`GET /api/v1/tasks/{task_id}/stream` streams task status updates (`PENDING`, `SUCCESS`, `FAILURE`) until completion.

## Example Usage

```bash
# Stream task progress
curl -N http://localhost:8000/api/v1/tasks/<task_id>/stream

# Import users via CSV
curl -X POST -H "Authorization: Bearer $TOKEN" -F "file=@users.csv" http://localhost:8000/api/v1/users/import/csv
```
