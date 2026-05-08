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
- **Middleware** (`app/middleware/`) – Correlation ID, logging, security, tenant resolution.
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
