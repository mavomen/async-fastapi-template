# CI/CD Documentation

The project uses **GitHub Actions** for continuous integration and deployment.

## Workflows

| Workflow                 | Trigger      | Purpose                                      |
| ------------------------ | ------------ | -------------------------------------------- |
| `test.yml`               | push, PR     | Run pytest with coverage, upload to Codecov  |
| `lint.yml`               | push, PR     | Lint code with Ruff                          |
| `typecheck.yml`          | push, PR     | Type check with mypy                         |
| `security.yml`           | push, weekly | Scan for vulnerabilities with Trivy          |
| `dependency-updates.yml` | weekly       | Create a PR with updated Poetry dependencies |

## Required Secrets

- `TEST_SECRET_KEY` – a 32‑char string for test JWT signing.
- Codecov token (optional for coverage upload).

## Running Locally

You can replicate the CI checks locally:

```bash
poetry run pytest --cov=app
poetry run ruff check .
poetry run mypy app/
```

## Extending

Add more workflows under .github/workflows/ following the same pattern.
