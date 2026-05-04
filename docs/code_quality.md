# Code Quality Guide

The project enforces code quality with **Ruff** (linting + formatting), **mypy** (strict type checking), and **pre-commit** hooks.

## Tools

- **Ruff**: Fast Python linter and formatter, replaces Flake8, isort, Black.
- **mypy**: Static type checker in strict mode.
- **pre-commit**: Runs checks automatically before each commit.

## Configuration

- `pyproject.toml` contains `[tool.ruff]` and `[tool.mypy]` sections.
- `.pre-commit-config.yaml` defines the hooks.

## Running Checks

```bash
# Lint and auto-fix
ruff check --fix .
ruff format .

# Type check
mypy app/

# Run all pre-commit hooks
pre-commit run --all-files
```

## Installing pre-commit

```bash
pre-commit install
```

After this, every `git commit` will trigger linting and formatting checks.

## Type Hints

All code must have complete type hints. mypy runs in strict mode. External libraries without stubs are excluded via ignore_missing_imports.

## CI Integration

GitHub Actions run these checks on every push (see CI/CD phase).
