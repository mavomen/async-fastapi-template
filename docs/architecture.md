# Architecture Decision Records (ADRs)

## ADR 1: Async SQLAlchemy 2.0

**Decision:** Use async SQLAlchemy 2.0 with `asyncpg` driver.
**Reason:** Maximises throughput, integrates naturally with FastAPI's async nature.

## ADR 2: JWT + RBAC Authentication

**Decision:** JWT for stateless auth, role‑based permissions stored in database.
**Reason:** Scales horizontally, fine‑grained access control.

## ADR 3: Celery for Background Tasks

**Decision:** Celery with Redis broker for long‑running tasks.
**Reason:** Reliable, well‑known, supports scheduling (Celery Beat).

## ADR 4: Local vs S3 File Storage

**Decision:** Abstract storage interface with local and S3 implementations.
**Reason:** Flexibility for development and production.

## ADR 5: Prometheus + Grafana for Observability

**Decision:** Prometheus metrics, Grafana dashboards, structured logging with structlog.
**Reason:** Open standards, easy integration, rich ecosystem.

## ADR 6: OpenTelemetry for Tracing

**Decision:** Optional OpenTelemetry integration with OTLP exporter.
**Reason:** Vendor‑neutral, future‑proof distributed tracing.

## ADR 7: Pydantic Settings vs python‑dotenv

**Decision:** pydantic‑settings for all configuration.
**Reason:** Validation, type safety, and easier management.

## ADR 8: ruff + mypy + pre‑commit

**Decision:** ruff for linting/formatting, mypy for type checking, pre‑commit hooks.
**Reason:** Fast, modern tools that catch errors early.

## ADR 9: Docker Multi‑stage Builds

**Decision:** Separate Dockerfiles for dev and prod, multi‑stage for prod.
**Reason:** Smaller production images, faster builds.
