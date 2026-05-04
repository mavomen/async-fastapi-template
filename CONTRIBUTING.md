# Contributing

Thank you for considering contributing to this project!

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/amazing-feature`).
3. Install dependencies: `poetry install`
4. Make your changes.
5. Run linters and tests: `poetry run ruff check . && poetry run mypy app/ && poetry run pytest`
6. Commit your changes (`git commit -m 'feat: add amazing feature'`).
7. Push to your branch (`git push origin feat/amazing-feature`).
8. Open a Pull Request.

## Development Setup

```bash
# Start services
docker compose -f docker-compose.dev.yml up -d

# Install dependencies
poetry install

# Run migrations
poetry run alembic upgrade head

# Start server
poetry run uvicorn app.main:app --reload
```

## Coding Conventions

- Follow PEP 8.
- Write type hints for all functions.
- Use async/await consistently.
- Add tests for new features (coverage must stay above 80%).
- Run `pre-commit install` before your first commit.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add new feature`
- `fix: correct a bug`
- `docs: update documentation`
- `test: add tests`
- `chore: maintenance tasks`

## Pull Request Process

1. Ensure all checks pass.
2. Update documentation if needed.
3. Request a review from a maintainer.
