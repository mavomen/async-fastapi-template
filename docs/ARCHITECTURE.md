# Architecture

## High‑Level Design

The application follows a **modular monolith** pattern organized into bounded contexts:

## Bounded Contexts

Domain logic lives in self-contained contexts under `app/`. Each context owns its models, Pydantic schemas, CRUD, services, Celery tasks, and HTTP endpoints:

| Context | Path | Owns |
|---------|------|------|
| Identity | `app/identity/` | Users, roles/RBAC, tenants, API keys, TOTP, WebAuthn, OAuth2, auth audit log, user GraphQL schema |
| Notifications | `app/notifications/` | In-app inbox, notification preferences, transactional email (Jinja2 templates in `app/templates/email/`), outgoing webhooks with HMAC signing |
| Billing | `app/billing/` | Plans catalog, per-tenant subscriptions with lifecycle state machine (trialing/active/past_due/canceled), hybrid proration, invoices from subscription periods (draft→open→paid, void-and-reissue), Stripe checkout + signed idempotent webhooks, Redis-backed usage metering with quota enforcement (429 over quota, fail-open) and overage-only invoice lines

**Shared kernel** (`app/models/`, `app/schemas/`, `app/crud/`): base classes and mixins (`BaseModel`, `TimestampMixin`, `SoftDeleteMixin`, `TenantBaseModel`), plus not-yet-contextualized models (audit log, task status, files, CMS pages/posts/categories/tags). Generic `CRUDBase` also lives here.

**Cross-cutting layers**: `app/api/` (composition root mounting all routers — prefixes/tags there define the public HTTP surface), `app/core/`, `app/middleware/`, `app/events/`, `app/websocket/`, `app/admin/`, `app/utils/`.

**Cross-context imports** are allowed only at documented seams:
- *Notifications → Identity*: dispatcher resolves recipient email/preferences via the user model.
- *Billing → Notifications* (planned): dunning emails go through the notifications context.
- *Orchestrators* (`app/tasks/purge.py`, admin views): coordinate across contexts by importing context-owned modules.

Everything else communicates through the event bus (`app/events/`) or Celery task boundaries.

## Layer Map (pre-refactor names)

- **API Layer** (`app/api/`) – FastAPI routes, dependencies, exception handlers, health checks.
- **Core** (`app/core/`) – Configuration, database, security, cache, metrics, tracing.
- **Models** (`app/models/` shared kernel + `app/<context>/models/`) – SQLAlchemy ORM models.
- **CRUD** (`app/crud/` shared kernel + per-context) – Generic and model‑specific database operations.
- **Schemas** (`app/schemas/` shared kernel + per-context) – Pydantic models for request/response validation.
- **Auth** (`app/identity/auth/`) – RBAC permissions, password hashing, JWT management.
- **Services / Tasks** – Per context (`app/identity/services/`, `app/notifications/tasks/`, …); generic tasks in `app/tasks/`.
- **Events** (`app/events/`) – Pluggable event bus (Redis Streams / Kafka).
- **WebSocket** (`app/websocket/`) – Chat with JWT auth.
- **Admin** (`app/admin/`) – HTMX‑powered dashboard.
- **Middleware** (`app/middleware/`) – Correlation ID, logging, security, tenant resolution, rate limiting.
- **Utils** (`app/utils/`) – Pagination, export, cache helpers.

## Data Flow

1. Request → Middleware chain (tenant, security, correlation) → Endpoint.
2. Endpoint → Dependency injection (DB session, cache, event bus) → Business logic.
3. Response → Serialized with ORJSON → Client.

## Multi‑Tenancy

Shared‑database architecture with a `tenant_id` column on every tenant‑scoped table. Row‑Level Security is enforced via SQLAlchemy events that automatically filter queries by the current tenant context.

## Event‑Driven Architecture

An abstract `EventBus` with two implementations:

- **Redis Streams** for lightweight pub/sub with consumer groups.
- **Kafka** for high‑throughput, durable event streaming.

Both are pluggable via configuration.

## Full‑Text Search

Users have a `search_vector` column that is automatically updated by a PostgreSQL trigger. The `SearchMixin` adds a `search_query` classmethod that generates a `WHERE search_vector @@ websearch_to_tsquery('english', <term>)` clause. Use it in any query to enable Google‑style full‑text search.

```python
from app.models.user import User
stmt = select(User).where(User.search_query("john doe"))
results = await db.execute(stmt)
```

```

## Audit Logging

Every INSERT, UPDATE, and DELETE on the `User` model (and any other model where `install_audit_log_listener` is called) is recorded in the `audit_logs` table. The audit log captures the table name, record ID, action, actor (if set via `_audit_actor_id`), and a JSON representation of changed fields.

The audit logs are visible in the admin dashboard as a read‑only table. To enable audit logging for additional models, call `install_audit_log_listener(MyModel)`.

## Feature Flags

Feature flags are managed via environment variables (`FEATURE_<NAME>={true|false}`), Redis cache, or defaults in `app/core/feature_flags.py`. The function `is_feature_enabled("flag")` checks sources in that order.

## Architecture Decision Records (ADRs)

### ADR 1: Async SQLAlchemy 2.0

**Decision:** Use async SQLAlchemy 2.0 with `asyncpg` driver.
**Reason:** Maximises throughput, integrates naturally with FastAPI's async nature.

### ADR 2: JWT + RBAC Authentication

**Decision:** JWT for stateless auth, role‑based permissions stored in database.
**Reason:** Scales horizontally, fine‑grained access control.

### ADR 3: Celery for Background Tasks

**Decision:** Celery with Redis broker for long‑running tasks.
**Reason:** Reliable, well‑known, supports scheduling (Celery Beat).

### ADR 4: Local vs S3 File Storage

**Decision:** Abstract storage interface with local and S3 implementations.
**Reason:** Flexibility for development and production.

### ADR 5: Prometheus + Grafana for Observability

**Decision:** Prometheus metrics, Grafana dashboards, structured logging with structlog.
**Reason:** Open standards, easy integration, rich ecosystem.

### ADR 6: OpenTelemetry for Tracing

**Decision:** Optional OpenTelemetry integration with OTLP exporter.
**Reason:** Vendor‑neutral, future‑proof distributed tracing.

### ADR 7: Pydantic Settings vs python‑dotenv

**Decision:** pydantic‑settings for all configuration.
**Reason:** Validation, type safety, and easier management.

### ADR 8: ruff + mypy + pre‑commit

**Decision:** ruff for linting/formatting, mypy for type checking, pre‑commit hooks.
**Reason:** Fast, modern tools that catch errors early.

### ADR 9: Docker Multi‑stage Builds

**Decision:** Separate Dockerfiles for dev and prod, multi‑stage for prod.
**Reason:** Smaller production images, faster builds.

### ADR 10: HTMX for Admin Dashboard

**Decision:** HTMX + server‑side rendering for the admin panel.
**Reason:** No JavaScript, stays in Python ecosystem, minimal dependencies.

### ADR 11: WebAuthn for Passwordless Authentication

**Decision:** WebAuthn for passkey support.
**Reason:** Modern, phishing‑resistant, user‑friendly.

### ADR 12: Multi‑Tenancy with RLS

**Decision:** Shared‑database + Row‑Level Security via SQLAlchemy events.
**Reason:** Simple to implement, no infrastructure changes, automatic query filtering.

### ADR 13: Feature Flags via Environment Variables

**Decision:** Feature flags with env-var, cache, and code defaults in that priority order.
**Reason:** Flexible, overridable at runtime without code changes.
