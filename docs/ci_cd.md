# CI/CD Documentation

The project uses **GitHub Actions** for continuous integration and deployment.

## Workflows

| Workflow           | Trigger               | Purpose                                            |
| ------------------ | --------------------- | -------------------------------------------------- |
| `test.yml`         | push, PR              | Matrix tests (Python 3.12/3.13), smoke test        |
| `lint.yml`         | push, PR              | Ruff linter                                        |
| `typecheck.yml`    | push, PR              | mypy type checking                                 |
| `docker-build.yml` | push to main, tags    | Docker build & push to ghcr.io                     |
| `deploy.yml`       | workflow_run (Docker) | SSH deploy to production                           |
| `security.yml`     | push, nightly         | Trivy vulnerability scan + safety dependency check |
| `release.yml`      | tag push, manual      | Automated changelog & GitHub release               |
| `pr-lint.yml`      | pull_request          | Semantic PR title + branch naming convention       |

All workflows use **Node.js 24** by setting `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`.

## Matrix Testing

Tests run against Python 3.12 and 3.13 in parallel.

## Self‑Hosted Runners

The release workflow includes a commented job for self‑hosted runners. Uncomment to use.

## Security Scanning

- **Trivy** scans for critical vulnerabilities in the filesystem.
- **Safety** checks Python dependency vulnerabilities (nightly).

## Release Automation

Pushing a `v*` tag automatically:

- Generates a changelog from conventional commits
- Creates a GitHub release with release notes

## PR Linting

- PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/)
- Branch names must follow `feat/*`, `fix/*`, `chore/*`, `docs/*`, `test/*`
