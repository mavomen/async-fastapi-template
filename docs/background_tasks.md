# Background Tasks

The application uses Celery with a Redis broker for background task processing.

## Architecture

- **Celery Worker** — executes tasks asynchronously
- **Celery Beat** — scheduled periodic tasks
- **Redis** — message broker and result backend

## Task Retry & Backoff

Tasks like email sending use exponential backoff with a configurable maximum retry count. On final exhaustion, a warning is logged.

## Monitoring

- Task status can be polled via `GET /api/v1/tasks/{task_id}`
- Celery worker metrics are exposed via Prometheus
- Worker logs are available via `docker compose logs -f celery_worker`
