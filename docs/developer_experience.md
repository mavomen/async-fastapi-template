# Developer Experience Guide

## CLI Tool

The project includes a Typer CLI for all common tasks. Run `poetry run python app/cli.py --help` to see available commands.

| Command             | Description                      |
| ------------------- | -------------------------------- |
| `install`           | Install dependencies with Poetry |
| `dev`               | Start development server         |
| `test`              | Run test suite (with coverage)   |
| `lint`              | Run linters (ruff + mypy)        |
| `lint --fix`        | Auto‑fix linting issues          |
| `migrate`           | Run database migrations          |
| `migrate --message` | Create a new Alembic migration   |
| `seed`              | Seed the database                |
| `docker`            | Start/stop Docker services       |
| `celery`            | Start Celery worker              |
| `graphql`           | Open GraphQL playground          |
| `load-test`         | Run Locust load tests            |
| `profile`           | Profile the application          |
| `scaffold`          | Interactive scaffolding tool     |
| `anonymise-db`      | Anonymise local development data |
| `verify-env`        | Check all services are running   |
| `setup`             | Full setup (install + migrate)   |

## Makefile

The Makefile is still available and delegates to the CLI for convenience.

## API Documentation

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **Scalar**: `/scalar` (modern, dark‑mode, interactive)

## Admin Dashboard

The admin dashboard includes a **dark mode toggle** (sun/moon button in the navbar). Preference is stored in `localStorage`.

## Kubernetes

Ready‑to‑use Kubernetes manifests are in the `k8s/` directory. A Helm chart is available in `helm/async-fastapi-template/`.

## VS Code

Recommended extensions are in `.vscode/extensions.json`. Debug configurations are in `.vscode/launch.json`.
