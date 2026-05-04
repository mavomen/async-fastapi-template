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

| Command            | Description                        |
| ------------------ | ---------------------------------- |
| `make install`     | Install Python dependencies        |
| `make dev`         | Start development server           |
| `make test`        | Run tests with coverage            |
| `make lint`        | Run all linting checks             |
| `make lint-fix`    | Auto‑fix linting issues            |
| `make migrate`     | Run database migrations            |
| `make migration`   | Create a new Alembic migration     |
| `make seed`        | Seed the database with sample data |
| `make docker-up`   | Start Docker services              |
| `make docker-down` | Stop Docker services               |
| `make celery`      | Start Celery worker                |
| `make setup`       | Full setup (install + migrate)     |

## VS Code

Recommended extensions are listed in `.vscode/extensions.json`. Open the project in VS Code and accept the prompt to install them.

Settings are pre‑configured for:

- Formatting on save with Ruff
- Strict type checking with mypy
- Pytest integration

## Scripts

- **`scripts/setup.sh`** – interactive setup script that starts Docker, installs deps, runs migrations, and optionally seeds the DB.
- **`scripts/seed.py`** – creates an admin user (`admin@example.com` / `Admin123!`) with full permissions and a normal user.

## Environment Variables

Copy `.env.example` to `.env` and adjust values for your local setup. The example file contains all available variables with sensible defaults for development.

## Project Conventions

- **Commit messages:** follow [Conventional Commits](https://www.conventionalcommits.org/)
- **Branch naming:** `feat/*`, `fix/*`, `chore/*`, `docs/*`, `test/*`
- **Code style:** enforced by Ruff and mypy
- **Testing:** minimum 80% coverage required
