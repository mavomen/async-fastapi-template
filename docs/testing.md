# Testing Guide

## Running Tests
```bash
poetry run pytest
```

## Test Organization
- `tests/api/` – endpoint tests
- `tests/core/` – config, database
- `tests/crud/` – database CRUD
- `tests/models/` – ORM models
- `tests/schemas/` – Pydantic schemas
- `tests/integration/` – multi‑step flows
- `tests/unit/` – isolated unit tests
- `tests/middleware/`, `tests/logging/`, etc.

## Coverage
Coverage is automatically collected with `--cov=app`. An HTML report is generated in `htmlcov/`.

Minimum coverage threshold: **80%**.

## Writing Tests
- Use `pytest` fixtures for reusable setup (database sessions, clients).
- Mock external services (Redis, S3, Celery) when testing business logic.
- Place integration tests that require a real database in `tests/integration/`.
- Keep unit tests fast and without I/O.

## CI
The test suite runs on every push via GitHub Actions (see `feat/ci`).
