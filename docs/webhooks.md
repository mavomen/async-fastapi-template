# Outgoing Webhooks

The template ships an outgoing webhook engine: domain events published on the event bus are
delivered to registered HTTPS endpoints with HMAC-SHA256 signatures, Celery retries with
exponential backoff, and a full delivery history for observability.

## How it works

1. A domain event is published to the event bus (`RedisStreamsEventBus` or `KafkaBus`).
2. The webhook dispatcher subscribes to all events (`"*"`) and finds every **active** webhook
   for the tenant whose `event_types` matches the event. A webhook with `event_types = null` or
   `[]` receives **all** events.
3. For each match, a `WebhookDelivery` row is created and the Celery task `deliver_webhook` is
   enqueued.
4. The task POSTs the signed payload to the endpoint URL with a timeout
   (`WEBHOOK_TIMEOUT_SECONDS`), records the outcome, and on failure schedules a retry with
   exponential backoff.

Delivery statuses: `pending`, `retrying`, `delivered`, `failed`.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `WEBHOOK_ENABLED` | `true` | Master switch for the dispatcher subscription |
| `WEBHOOK_MAX_RETRIES` | `5` | Maximum Celery retries per delivery |
| `WEBHOOK_BACKOFF_BASE_SECONDS` | `60.0` | Initial backoff; doubles per attempt |
| `WEBHOOK_BACKOFF_MAX_SECONDS` | `3600.0` | Backoff cap |
| `WEBHOOK_TIMEOUT_SECONDS` | `10` | Outbound HTTP timeout |
| `WEBHOOK_SIGNATURE_TOLERANCE_SECONDS` | `300` | Replay tolerance for signature verification |

## Management API

All routes live under `/api/v1/webhooks` and are tenant-scoped. `webhook:read` /
`webhook:write` permissions are seeded; write operations require `webhook:write`.

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhooks` | Create a webhook; returns the signing `secret` **once** |
| `GET` | `/webhooks` | List webhooks for the tenant |
| `GET` | `/webhooks/{id}` | Fetch one webhook |
| `PATCH` | `/webhooks/{id}` | Update name, URL, event subscriptions, active flag |
| `DELETE` | `/webhooks/{id}` | Delete webhook and delivery history |
| `POST` | `/webhooks/{id}/ping` | Enqueue a synthetic `webhook.test` delivery |
| `GET` | `/webhooks/{id}/deliveries` | Delivery history |

The signing secret is generated server-side (`secrets.token_urlsafe(32)`) and returned only in
the create response. It is never exposed again by list/get endpoints — rotate it by deleting and
recreating the webhook.

## Request signing

Every delivery POST includes:

```
X-Webhook-Signature: t=<unix_ts>,v1=<hex_hmac_sha256>
X-Webhook-Event: user.created
X-Webhook-Id: <event_id>
X-Webhook-Delivery: <delivery_id>
X-Webhook-Attempt: 1
```

The HMAC is computed over the raw request body using the webhook secret. Recipients should verify
the timestamp is within `WEBHOOK_SIGNATURE_TOLERANCE_SECONDS` of now and compare the digest with
a constant-time comparison (`hmac.compare_digest`).

```python
# recipient verification (synchronous example)
import hmac
import time

def verify(secret: bytes, body: bytes, header: str) -> bool:
    fields = dict(part.split("=") for part in header.split(","))
    if abs(int(fields["t"]) - time.time()) > 300:
        return False
    expected = "v1=" + hmac.new(secret, body, "sha256").hexdigest()
    return hmac.compare_digest(header, f"t={fields['t']},{expected}")
```

## Retry & backoff

Failed deliveries retry `WEBHOOK_MAX_RETRIES` times with
`countdown = min(WEBHOOK_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1), WEBHOOK_BACKOFF_MAX_SECONDS)`.
A delivery record carries `attempt` / `max_attempts` (`max_retries + 1`). Before the final
attempt the status is `retrying` with a `next_retry_at` timestamp; the final failure sets
`failed` and increments the webhook's `failure_count`. A successful delivery resets the counter.

Disabling a webhook (`is_active = false`) stops new deliveries; already-enqueued deliveries are
marked `failed` with error `webhook disabled`.

## Events & dispatcher

The dispatcher registers a wildcard handler on the event bus so it sees every event without a
per-type subscription list. Dispatch runs inside a dedicated DB session and never raises into the
consumer loop: failures are logged and swallowed so the event bus keeps consuming.

## Data model

- `webhooks` — `name`, `url`, `secret`, `event_types` (JSON), `is_active`, `last_delivery_at`,
  `last_status`, `failure_count`; tenant-scoped via `TenantBaseModel`.
- `webhook_deliveries` — `webhook_id`, `event_id`, `event_type`, `payload` (JSON), `attempt`,
  `max_attempts`, `status`, `response_status`, `response_body`, `error`, `next_retry_at`,
  `delivered_at`.

Both are created by Alembic revision `013_add_webhooks`.
