# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- Billing foundation (`app/billing/`): plan catalog (prices in minor units, monthly/yearly
  intervals, trial days) and per-tenant subscriptions with an enforced lifecycle state
  machine (trialing → active → past_due → canceled), at most one live subscription per
  tenant (partial unique index), hybrid proration (upgrades apply immediately with
  unused-time credit; downgrades schedule at period end), cancel/resume, and lifecycle
  events on the event bus. REST surface: `/api/v1/billing/plans`,
  `/api/v1/billing/subscriptions`; `billing:read` / `billing:write` permissions;
  migration `018_add_billing_tables`
- Stripe integration (`app/billing/services/stripe_*`, `/api/v1/billing/stripe/*`):
  dependency-free async Stripe REST client over httpx (customer provisioning, hosted
  checkout sessions with inline `price_data`, subscription fetch), signature-verified
  inbound webhooks (`Stripe-Signature` via shared `app/core/signing.py`), and idempotent
  event processing backed by a `stripe_events` ledger — `checkout.session.completed`,
  `customer.subscription.updated/deleted`, and `invoice.payment_failed` drive the local
  subscription lifecycle. Disabled (503) until `STRIPE_SECRET_KEY` /
  `STRIPE_WEBHOOK_SECRET` are set; migration `019_add_stripe_integration`
- Invoicing (`app/billing/services/invoicing.py`, `/api/v1/billing/invoices/*`): invoices
  generated from subscription periods with plan pricing snapshotted into line items,
  VAT/tax captured per line in basis points, and a draft → open → paid state machine
  (void reachable from draft/open; a partial unique index allows re-issue after voiding).
  Invoice numbers are derived from the primary key (`INV-{year}-{id}`); PDF rendering is
  deferred. Daily Celery sweep issues invoices for ended periods (idempotent);
  `billing:read` / `billing:write` permissions; migration `020_add_invoicing`
- Usage metering (`app/billing/services/usage.py`, `app/billing/api/deps.py`): Redis-backed
  period-scoped counters per metered dimension (`plans.metering` JSON, migration
  `021_add_plan_metering`). Authenticated API routes enforce plan quotas (429 over quota,
  fail-open on internal errors) behind `BILLING_QUOTA_ENABLED` (default off). Invoices
  append overage-only lines (`max(0, used - included)` × unit price); new
  `GET /api/v1/billing/subscriptions/usage` reports current-period usage
- Dunning (`app/billing/services/dunning.py`, `app/tasks/dunning.py`): payment-failure
  retry schedule with exponential backoff (`base * 2**(N-1)`, 7-day cap), reminder and
  suspension sweeps every 15 minutes behind `BILLING_DUNNING_ENABLED` (default off), new
  terminal `suspended` subscription status, recovery on successful payment (past_due ->
  active via invoice capture or Stripe sync), and `billing.dunning.*` events fanned out
  to active tenant users through the notifications pipeline; migration `022_add_dunning`
- Admin billing actions (`app/admin/__init__.py`, `app/admin/templates/actions_row.html`):
  `POST /admin/subscriptions/{id}/override-plan` swaps a subscription to another active
  plan immediately (period reset via `next_period_end`), `POST /admin/subscriptions/{id}/set-status`
  walks the validated status transition graph (updates `canceled_at`/`suspended_at`, resets
  dunning bookkeeping), and `POST /admin/invoices/{id}/refund` issues a real Stripe refund
  (`create_refund` on `pi_`/`charge_` references; 503 when Stripe is unconfigured, 502 on
  upstream 5xx). New tables register with `deletable=False` and lifecycle fields excluded
  from generic forms.

## [3.5.0] - 2026-08-21

### Changed

- Internal restructure of `app/` into bounded contexts: `identity/` (users, RBAC,
  tenants, API keys, TOTP, WebAuthn, OAuth2, auth audit, user GraphQL), `notifications/`
  (inbox, preferences, email, webhooks), and a reserved `billing/` scaffold. Shared
  base models, CMS, files, task status, and the audit log remain in the `app/models/`
  shared kernel. No HTTP behavior change — routes, prefixes, and tags are identical
  (OpenAPI snapshot unchanged); import paths for moved modules changed accordingly.

### Added

- Outgoing webhook engine: HMAC‑SHA256 signed deliveries for domain events, Celery retries
  with exponential backoff, delivery history, ping endpoint, and REST management API
  (`POST/GET/PATCH/DELETE /api/v1/webhooks`, `POST /{id}/ping`, `GET /{id}/deliveries`)
- `webhook:read` and `webhook:write` permissions
- Alembic migration `013_add_webhooks` (`webhooks`, `webhook_deliveries` tables)
- Per-user notification preferences (email / in-app / webhook channels) with self-service
  `GET|PUT /api/v1/notifications/preferences`
- In-app notification inbox with list / mark-read / mark-all-read / delete endpoints
  (`GET /api/v1/notifications`, `POST /{id}/read`, `POST /read-all`, `DELETE /{id}`) and a
  best-effort WebSocket push to the user's live sessions
- `POST /api/v1/notifications/test` to publish a test notification through the event bus;
  events now carry an optional `user_id` used to gate channel delivery
- Webhook dispatcher suppresses deliveries for events whose actor disabled the webhook channel
- Alembic migration `014_add_notifications` (`notification_preferences`, `notifications` tables)
- Cursor-based keyset pagination for `GET /api/v1/notifications` (DESC order, `cursor`/`size`
  params, `next_cursor`/`has_more` response fields)
- `CursorParams`, `CursorPage` exported from `app.utils`
- `NotificationCursorResponse` schema for the paginated notification inbox
- Bulk CSV user import rewritten to single-commit `add_all()` with pre-query duplicate
  filtering and off-event-loop bcrypt hashing via `asyncio.to_thread`
- Per-environment pool tuning: `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` resolve from
  `ENVIRONMENT` presets when unset (dev=10/5, staging=20/10, prod=40/20)
- Prometheus gauges `db_pool_active`, `db_pool_idle`, `db_pool_overflow`,
  `db_pool_waiting` (in-flight checkout proxy)
- `InstrumentedQueuePool` subclass for waiting-connection gauge
- Automated PostgreSQL backup via Celery beat: `pg_dump` → gzip → S3 with configurable
  `BACKUP_S3_PREFIX` and `BACKUP_RETENTION_DAYS` (default 30)
- Celery `cleanup_old_backups` task deletes expired backups from S3 daily
- `restore_backup` task for manual point-in-time restore (downloads latest or explicit key)
- MinIO service in `docker-compose.dev.yml` for local S3-compatible backup testing
- Weekly CI restore-drill workflow (`.github/workflows/backup-restore-drill.yml`)
- Pre-commit hooks: `poetry check --lock`, `pip-audit`, `detect-secrets` with baseline
- Error catalog: all API error responses now include an `error_code` field
  (`NOT_FOUND`, `BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, `CONFLICT`,
  `LOCKED_OUT`, `INTERNAL_ERROR`, `VALIDATION_ERROR`, `HTTP_ERROR`)
- New `RateLimitException` (HTTP 429) for explicit rate-limit error responses
- Mypy strict mode tightened: removed blanket `ignore_missing_imports = true`; only
  untyped libraries (`kafka`, `brotli`, `boto3`, `openpyxl`) retain per-module overrides
- OpenTelemetry `TracerProvider` now sets `Resource` attributes (`service.name`,
  `service.version`, `deployment.environment`) so Grafana Tempo can group and filter traces
- Configurable `OTEL_SERVICE_NAME` and `OTEL_SAMPLE_RATE` (`TraceIdRatioBased`) settings
- `TracerProvider.shutdown()` called during app lifespan for graceful span flushing
- Grafana Tempo service added to `docker-compose.yml` and `docker-compose.dev.yml`
- Grafana Tempo datasource auto-provisioned with traces-to-logs correlation
- Trace-log correlation: `trace_id` and `span_id` are now injected into every structlog
  context via `RequestIDMiddleware`, enabling direct log-to-trace navigation in Grafana
- Configurable `OTEL_SAMPLE_RATE` controls span sampling via `TraceIdRatioBased`

### Fixed

- Brotli/gzip compression middleware returned an empty body for responses below the minimum
  compression size; streaming responses from `BaseHTTPMiddleware` (`_StreamingResponse`) are
  now handled correctly

### Changed

- `GET /api/v1/notifications` now uses cursor pagination (`cursor`/`size` query params)
  instead of `skip`/`limit`; response shape changed to `NotificationCursorResponse`
  (no `total` field; `next_cursor`, `has_more`, `size`, `unread_count` instead)

## [3.1.0] — 2026‑05‑11

### Added

- Refresh token support with token rotation on refresh
- Database‑backed WebAuthn credential store (replaces in‑memory dict)
- OpenAPI schema snapshot test (syrupy)
- Mutation testing workflow (mutmut) in CI
- Admin dashboard duplicate email validation with proper 400 errors
- Test coverage raised to 85% minimum threshold
- Additional test files for edge cases across the codebase

### Changed

- Updated `.env.example` with all current settings (WebAuthn, event bus, feature flags, performance)
- Aligned Celery Redis DB numbers in docker‑compose with config defaults
- Audited audit logging installation – now wired into app startup (guarded in test env)
- GraphQL subscription connected to config‑driven EventBus (Redis / Kafka)

### Fixed

- WebAuthn credential functions now accept `db` dependency consistently
- Mypy errors in `profile.py` and `webauthn.py` resolved
- Ruff docstring nits corrected across multiple test files

## [3.0.0] — 2026‑05‑09

### Added

- WebAuthn / Passkey registration and authentication endpoints
- RS256 asymmetric JWT support with JWKS endpoint
- Per‑user rate limiting (JWT sub‑based)
- Request ID injection into structlog context and OpenTelemetry spans
- HTMX‑powered admin dashboard with auto‑discovery of SQLAlchemy models
- Multi‑tenancy with Row‑Level Security via SQLAlchemy events
- Full‑text search on User model (PostgreSQL tsvector)
- Audit logging with SQLAlchemy event listeners
- Feature flag system (env, Redis, code defaults)
- Pluggable EventBus (Redis Streams / Kafka) with Celery consumer and WebSocket bridge
- Typer CLI (replaces Makefile for all commands)
- Scalar API reference at `/scalar`
- Kubernetes manifests and Helm chart
- Dark mode toggle for admin dashboard
- SQL query count middleware with Prometheus histogram
- Performance benchmark regression CI job
- Test coverage raised to 85%

### Changed

- Bumped version from 1.0.1 to 3.0.0
- Switched SSE implementation from `sse-starlette` to manual `StreamingResponse`
- Moved dependency installation from `pip` to Poetry in Dockerfiles
- Updated `.env.example` with new settings

### Fixed

- Cache `connect()` method implementation
- Application lifespan now connects and disconnects cache
- Production Dockerfile runs as non‑root user with healthcheck
- CI test secret falls back to default
- Deploy workflow gated on SSH secrets existence
- Health check Redis connection pool now reuses cache singleton
- Admin duplicate email returns 400 instead of 500

## [2.0.0] — 2026‑05‑08

### Added

- GraphQL endpoint with Strawberry (queries, mutations, subscriptions)
- Query profiling middleware and slow‑query logging
- Redis pipelining utilities for batch operations
- Bulk user creation and CSV import endpoints
- Cache warming and cache‑aside pattern utilities
- Email retry with exponential backoff via Celery
- Streaming file upload with SSE progress
- SSE endpoint for background task status
- Locust load‑testing scripts and pytest benchmarks
- PR title and branch name linting
- Automated release workflow with changelog generation
- Nightly vulnerability scan (Safety + Trivy)
- Interactive scaffolding CLI (`make scaffold`)
- Database anonymisation script
- Environment verification script
- VS Code debug launch configuration
- Issue templates (bug report, feature request) and PR template
- FAQ documentation

### Changed

- Updated Docker Compose to use Postgres 18‑alpine tag
- Separated Redis database numbers for cache, Celery broker, and results
- CI workflows migrated to Node 24
- Test matrix now includes Python 3.12 and 3.13
- Converted SSE implementation from `sse-starlette` to manual `StreamingResponse`
- Updated `python-json-logger` import to non‑deprecated path
- Updated all README badges and comparison table

### Fixed

- Cache `connect()` method now properly initialises Redis client
- Application lifespan now connects and disconnects cache
- Production Dockerfile now runs as non‑root user with healthcheck
- CI test secret now falls back to a safe default
- Deploy workflow gated on SSH secrets existence
- Circular import between `deps.py` and `permissions.py`
- Slow‑query profiling compatible with test NullPool

## [1.0.1] — 2026‑05‑04

### Fixed

- Cache `connect()` method implementation
- Lifespan cache initialisation
- Production Dockerfile non‑root user and healthcheck
- CI test secret fallback
- Deploy workflow gating on SSH secrets
- Postgres image tag in Docker Compose
- Redis DB separation for cache, Celery broker, and results
- `python-json-logger` import path
- Root logger configuration in development mode
- README organisation placeholders

## [1.0.0] — 2026‑05‑04

### Added

- Initial release with async SQLAlchemy 2.0, JWT auth, RBAC
- Celery background tasks, Redis caching, rate limiting
- File uploads (local + S3), WebSocket chat
- Prometheus metrics, Grafana dashboards, OpenTelemetry tracing
- Structured logging, security headers, XSS/SQL injection protection
- Email verification, CSV/Excel export
- Docker Compose for dev and production
- CI/CD workflows for testing, linting, type checking, security scanning
- Comprehensive test suite (80%+ coverage)
- Extensive documentation set

[3.1.0]: https://github.com/mavomen/async-fastapi-template/releases/tag/v3.1.0
[3.0.0]: https://github.com/mavomen/async-fastapi-template/releases/tag/v3.0.0
[2.0.0]: https://github.com/mavomen/async-fastapi-template/releases/tag/v2.0.0
[1.0.1]: https://github.com/mavomen/async-fastapi-template/releases/tag/v1.0.1
[1.0.0]: https://github.com/mavomen/async-fastapi-template/releases/tag/v1.0.0
