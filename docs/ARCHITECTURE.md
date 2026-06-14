# Architecture

## High‑Level Design

The application follows a **modular monolith** pattern with clear separation of concerns:

- **API Layer** (`app/api/`) – FastAPI routes, dependencies, exception handlers, health checks.
- **Core** (`app/core/`) – Configuration, database, security, cache, metrics, tracing.
- **Models** (`app/models/`) – SQLAlchemy ORM models (User, Role, Permission, Tenant, TaskStatus).
- **CRUD** (`app/crud/`) – Generic and model‑specific database operations.
- **Schemas** (`app/schemas/`) – Pydantic models for request/response validation.
- **Auth** (`app/auth/`) – RBAC permissions, password hashing, JWT management.
- **Services** (`app/services/`) – Email service with Jinja2 templates.
- **Tasks** (`app/tasks/`) – Celery background tasks.
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
