# Async FastAPI Template

[![Lint](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/lint.yml/badge.svg)](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/lint.yml)
[![Type Check](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/typecheck.yml/badge.svg)](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/typecheck.yml)
[![Test](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/test.yml/badge.svg)](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/test.yml)
[![Security Scan](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/security.yml/badge.svg)](https://github.com/mavomen-org/async-fastapi-template/actions/workflows/security.yml)

A production‑ready, fully async FastAPI template with:

- ⚡ Async SQLAlchemy 2.0 + Alembic
- 🔐 JWT auth + RBAC (roles & permissions)
- 🚀 Background tasks (Celery + Redis)
- 📦 File uploads (local / S3)
- 🗨️ WebSocket support
- 📊 Prometheus metrics, Grafana dashboards
- 🕵️ Distributed tracing (OpenTelemetry)
- ⚡ Rate limiting, caching, structured logging
- 🐳 Docker & Docker Compose (dev + prod)
- ✅ CI/CD workflows (GitHub Actions)
- 🧪 80%+ test coverage

## Quickstart

```bash
git clone https://github.com/mavomen-org/async-fastapi-template.git
cd async-fastapi-template
cp .env.example .env
docker compose up -d
poetry install
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs

## Documentation

- [Quickstart Guide](docs/quickstart.md)
- [API Documentation](docs/api.md)
- [Architecture Decisions](docs/architecture.md)
- [Database Setup](docs/database.md)
- [Docker Guide](docs/docker.md)
- [Background Tasks](docs/background_tasks.md)
- [Caching Strategy](docs/caching.md)
- [Rate Limiting](docs/rate_limiting.md)
- [File Storage](docs/file_storage.md)
- [WebSocket Usage](docs/websocket.md)
- [Logging](docs/logging.md)
- [Metrics & Monitoring](docs/metrics.md)
- [Health Checks](docs/health.md)
- [Distributed Tracing](docs/tracing.md)
- [Testing Guide](docs/testing.md)
- [Code Quality](docs/code_quality.md)
- [CI/CD](docs/ci_cd.md)
- [Deployment](docs/deployment.md)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
