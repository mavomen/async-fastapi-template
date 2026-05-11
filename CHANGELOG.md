# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
