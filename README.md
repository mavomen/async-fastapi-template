# Async FastAPI Template

[![Test](https://github.com/mavomen/async-fastapi-template/actions/workflows/test.yml/badge.svg)](https://github.com/mavomen/async-fastapi-template/actions/workflows/test.yml)
[![Lint](https://github.com/mavomen/async-fastapi-template/actions/workflows/lint.yml/badge.svg)](https://github.com/mavomen/async-fastapi-template/actions/workflows/lint.yml)
[![Type Check](https://github.com/mavomen/async-fastapi-template/actions/workflows/typecheck.yml/badge.svg)](https://github.com/mavomen/async-fastapi-template/actions/workflows/typecheck.yml)
[![Security Scan](https://github.com/mavomen/async-fastapi-template/actions/workflows/security.yml/badge.svg)](https://github.com/mavomen/async-fastapi-template/actions/workflows/security.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)](https://github.com/mavomen/async-fastapi-template)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A production‑ready, fully async FastAPI template with everything you need to build modern APIs.

## 🚀 Features

- ⚡ **Async SQLAlchemy 2.0** + Alembic migrations
- 🔐 **JWT authentication** with role‑based access control (RBAC)
- 🧬 **GraphQL** endpoint with Strawberry (queries, mutations, subscriptions)
- 📦 **File uploads** (local & S3) with streaming progress
- 🗨️ **WebSocket** chat with JWT auth
- ⏳ **Background tasks** with Celery + Redis + retry/backoff
- 💾 **Redis caching** with cache‑aside, warming, and invalidation
- 🚦 **Rate limiting** with slowapi
- 📊 **Prometheus metrics** + **Grafana dashboards**
- 🕵️ **Distributed tracing** with OpenTelemetry
- ✉️ **Email verification** with Jinja2 templates and Celery retry
- 📥 **CSV / Excel export and import** utilities
- 🛡️ **Security headers**, SQL injection monitoring, XSS sanitisation
- 📝 **Structured logging** with structlog and correlation IDs
- ⚡ **Performance profiling** (slow‑query logging, benchmarks, load tests)
- 🛠️ **Scaffolding CLI** – generate models, endpoints, and tests instantly
- 🐳 **Docker Compose** for dev and production
- 🔧 **CI/CD workflows** (matrix tests, PR linting, automated releases)
- 🧹 **Code quality** enforced by Ruff, mypy, and pre‑commit
- 📖 **Extensive documentation** – quickstart, architecture, deployment, and more

## 📸 Screenshots

| Swagger UI     | GraphQL Playground | Grafana Dashboard |
| -------------- | ------------------ | ----------------- |
| _[screenshot]_ | _[screenshot]_     | _[screenshot]_    |

## 🏁 Quickstart

```bash
git clone https://github.com/mavomen/async-fastapi-template.git
cd async-fastapi-template
chmod +x scripts/setup.sh && ./scripts/setup.sh
make dev
```

Visit **http://localhost:8000/docs** for the interactive API docs, or **http://localhost:8000/graphql** for the GraphQL playground.

## 📋 How does it compare?

| Feature                    | This Template | Other Templates |
| -------------------------- | ------------- | --------------- |
| Async DB (SQLAlchemy 2)    | ✅            | ❌              |
| RBAC (roles/permissions)   | ✅            | ❌              |
| GraphQL                    | ✅            | ❌              |
| Celery + Retry/Backoff     | ✅            | ❌              |
| File uploads (S3/local)    | ✅            | ❌              |
| WebSocket                  | ✅            | ❌              |
| Rate limiting              | ✅            | ❌              |
| Prometheus + Grafana       | ✅            | ❌              |
| OpenTelemetry tracing      | ✅            | ❌              |
| Email verification         | ✅            | ❌              |
| CSV/Excel export/import    | ✅            | ❌              |
| Streaming uploads (SSE)    | ✅            | ❌              |
| Cache warming & aside      | ✅            | ❌              |
| Scaffolding CLI            | ✅            | ❌              |
| Docker dev + prod          | ✅            | ✅              |
| CI/CD + Release automation | ✅            | ✅              |
| 85%+ test coverage         | ✅            | ❌              |

## 📚 Documentation

- [Quickstart Guide](docs/quickstart.md)
- [API Documentation](docs/api.md)
- [GraphQL Guide](docs/graphql.md)
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
- [Performance Tuning](docs/performance.md)
- [Email & Export](docs/additional_features.md)
- [Testing Guide](docs/testing.md)
- [Code Quality](docs/code_quality.md)
- [CI/CD](docs/ci_cd.md)
- [Deployment](docs/deployment.md)
- [Developer Experience](docs/developer_experience.md)
- [FAQ](docs/faq.md)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## 🗺️ Roadmap

- [x] Core FastAPI app with async SQLAlchemy
- [x] JWT auth and RBAC
- [x] Background tasks, caching, rate limiting
- [x] File storage, WebSocket, email verification
- [x] GraphQL integration
- [x] Performance profiling & load testing
- [x] CI/CD polish & release automation
- [x] Advanced features (SSE, cache warming, batch ops)
- [x] Developer tooling (scaffolder, scripts)
- [ ] Admin dashboard (HTMX or React)
- [ ] Multi‑tenancy support
- [ ] Event‑driven architecture (Kafka/RabbitMQ)

Have an idea? Open an issue or a pull request!

## ❓ FAQ

**Q: Can I use this for a production project?**
A: Yes! The template follows best practices and includes production‑ready configurations. Just replace the default secrets and configure your own infrastructure.

**Q: Do I need Redis?**
A: Redis is used for caching, rate limiting, and Celery. You can disable these features if you don't need Redis, but it's recommended.

**Q: How do I add a new feature?**
A: Run `make scaffold` to generate a model, endpoint, and tests. See the [Developer Experience Guide](docs/developer_experience.md).

**Q: How do I contribute?**
A: Read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting pull requests.

## 📄 License

MIT License — see the [LICENSE](LICENSE) file for details.
