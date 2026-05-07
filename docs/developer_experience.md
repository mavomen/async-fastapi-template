# Developer Experience Guide

## Quickstart

```bash
# One‑time setup
chmod +x scripts/setup.sh && ./scripts/setup.sh

# Start developing
make dev
```

## Makefile Commands

Run `make` or `make help` to see all available commands.

| Command             | Description                                  |
| ------------------- | -------------------------------------------- |
| `make install`      | Install Python dependencies                  |
| `make dev`          | Start development server                     |
| `make test`         | Run tests with coverage                      |
| `make lint`         | Run all linting checks                       |
| `make lint-fix`     | Auto‑fix linting issues                      |
| `make migrate`      | Run database migrations                      |
| `make migration`    | Create a new Alembic migration               |
| `make seed`         | Seed the database with sample data           |
| `make graphql`      | Open GraphQL playground in browser           |
| `make load-test`    | Start Locust load tests                      |
| `make profile`      | Profile the app with py‑spy                  |
| `make scaffold`     | Interactive CLI wizard (model/endpoint/test) |
| `make anonymise-db` | Anonymise local PII data                     |
| `make verify-env`   | Check all services are running               |
| `make docker-up`    | Start Docker services                        |
| `make docker-down`  | Stop Docker services                         |
| `make celery`       | Start Celery worker                          |
| `make setup`        | Full setup (install + migrate)               |

## Scaffolding Tool

Run `make scaffold` or `poetry run python scripts/scaffold.py` to interactively generate:

- SQLAlchemy model
- Pydantic schemas
- CRUD module
- API endpoints
- Pytest test file

Just follow the prompts!

## VS Code

Recommended extensions are listed in `.vscode/extensions.json`. Open the project in VS Code and accept the prompt to install them.

Settings are pre‑configured for:

- Formatting on save with Ruff
- Strict type checking with mypy
- Pytest integration
- Debug launch configurations for FastAPI and tests (`.vscode/launch.json`)

## Scripts

- **`scripts/setup.sh`** – interactive setup script.
- **`scripts/seed.py`** – creates an admin user with full permissions.
- **`scripts/anonymise_db.py`** – replaces PII in the local database.
- **`scripts/verify_env.py`** – checks database and Redis connectivity.
- **`scripts/scaffold.py`** – generates boilerplate from a template.

## Environment Variables

Copy `.env.example` to `.env` and adjust values for your local setup.
