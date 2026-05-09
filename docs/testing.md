# Testing Guide

## Running Tests

```bash
poetry run pytest --cov=app --cov-report=html
```

## Test Organization

- `tests/api/` – endpoint tests
- `tests/core/` – config, database, cache, metrics
- `tests/crud/` – database CRUD
- `tests/models/` – ORM models
- `tests/schemas/` – Pydantic schemas
- `tests/integration/` – multi‑step flows
- `tests/unit/` – isolated unit tests
- `tests/admin/` – HTMX admin dashboard
- `tests/architecture/` – search, audit, feature flags
- `tests/events/` – event bus (Redis/Kafka)
- `tests/gql/` – GraphQL
- `tests/cli/` – Typer CLI
- `tests/tenant/` – multi‑tenancy
- `tests/middleware/` – custom middlewares

## Coverage

Minimum threshold: **85%**.  
Run `poetry run pytest --cov=app` to see the report.  
An HTML report is generated in `htmlcov/`.

## Snapshot Testing

OpenAPI schema changes are caught by a snapshot test (`tests/contract/test_openapi_snapshot.py`).  
If you intentionally change the API, update the snapshot with:

```bash
poetry run pytest --snapshot-update
```

## Mutation Testing

[Mutmut](https://mutmut.readthedocs.io/) runs weekly in CI and can be triggered manually.  
It mutates source code and checks if tests still pass.  
Run locally with:

```bash
poetry run mutmut run --paths-to-mutate app/
```

## Writing Tests

- Use `pytest` fixtures for reusable setup (database sessions, clients).
- Mock external services (Redis, S3, Celery) when testing business logic.
- Keep unit tests fast and without I/O.
- Add snapshot tests for stable API contracts.

## CI

Tests run on every push via GitHub Actions (Python 3.12 & 3.13).  
Coverage must stay at or above 85%.  
Mutation testing runs every Sunday to validate test quality.
