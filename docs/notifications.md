# Notification Preferences & In-App Inbox

Per-user opt-in/opt-out for the **email**, **in-app**, and **webhook** notification channels,
with a persisted in-app inbox and best-effort WebSocket push.

## How it works

1. A domain event is published to the event bus with an optional `user_id` (the event actor).
2. The notification dispatcher subscribes to all events (`"*"`) and, for events carrying a
   `user_id`, checks that user's channel preferences.
3. For each enabled channel the event is delivered:
   - **in-app** — a `Notification` row is inserted into the user's inbox and pushed over
     WebSocket to any live session (`/ws`), best-effort.
   - **email** — the Celery task `send_email_with_retry` renders `notification.html` and sends.
   - **webhook** — the webhook dispatcher skips tenant webhook deliveries for events whose actor
     has the webhook channel disabled (actor-level suppression).

Users with **no preference row default to all channels enabled**. Transactional auth emails
(verification, magic-link) are never suppressed by preferences.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `NOTIFICATION_ENABLED` | `true` | Master switch for the notification dispatcher subscription |

## Preferences API

All routes live under `/api/v1/notifications` and are self-service (authenticated user only).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/notifications/preferences` | Get the current user's channel preferences (creates defaults on first read) |
| `PUT` | `/notifications/preferences` | Update channel opt-ins, e.g. `{"email_enabled": false}` |

```json
{
  "email_enabled": true,
  "in_app_enabled": true,
  "webhook_enabled": false
}
```

## Inbox API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/notifications` | List the user's notifications (newest first); supports `skip`, `limit`, `unread_only` |
| `POST` | `/notifications/{id}/read` | Mark one notification as read |
| `POST` | `/notifications/read-all` | Mark all unread notifications as read |
| `DELETE` | `/notifications/{id}` | Delete one notification |
| `POST` | `/notifications/test` | Publish a `notification.test` event for the current user (exercises in-app + email) |

`GET /notifications` returns `{items, total, unread_count}`. Accessing another user's
notification returns `404` (existence is not leaked).

## Publishing a notification

Events must carry the actor id and a human-readable payload:

```python
from app.events.base import Event

event = Event(
    event_type="user.created",
    payload={"title": "Welcome", "body": "Your account is ready"},
    user_id=user.id,
)
await bus.publish(event)
```

The dispatcher derives the title/body from the `title`/`body` payload keys and falls back to the
event type when absent.

## Data model

- `notification_preferences` — `user_id` (unique, FK cascade), `email_enabled`,
  `in_app_enabled`, `webhook_enabled`.
- `notifications` — `user_id`, `event_type`, `title`, `body`, `is_read`, `read_at`; indexed on
  `(user_id, is_read)`.

Both are created by Alembic revision `014_add_notifications`. Both models are user-scoped
(not tenant-scoped) and are exposed in the admin dashboard under the `notification:admin`
permission.
