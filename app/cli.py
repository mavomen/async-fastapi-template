#!/usr/bin/env python3
"""Typer CLI for the FastAPI template."""

import subprocess

import typer

app = typer.Typer(
    name="fastapi-template",
    help="CLI for the async-FastAPI template.",
    add_completion=True,
)


@app.command()
def install() -> None:
    """Install Python dependencies via Poetry."""
    subprocess.run(["poetry", "install"], check=True)


@app.command()
def dev(host: str = "0.0.0.0", port: int = 8000, reload: bool = True) -> None:  # nosec B104
    """Start the development server."""
    cmd = ["poetry", "run", "uvicorn", "app.main:app", "--host", host, f"--port={port}"]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, check=True)


@app.command()
def test(coverage: bool = True, html: bool = True) -> None:
    """Run the test suite."""
    cmd = ["poetry", "run", "pytest"]
    if coverage:
        cmd.append("--cov=app")
        if html:
            cmd.append("--cov-report=html")
    subprocess.run(cmd, check=True)


@app.command()
def lint(fix: bool = False) -> None:
    """Run linting checks."""
    if fix:
        subprocess.run(["poetry", "run", "ruff", "check", "--fix", "."], check=True)
        subprocess.run(["poetry", "run", "ruff", "format", "."], check=True)
    else:
        subprocess.run(["poetry", "run", "ruff", "check", "."], check=True)
        subprocess.run(["poetry", "run", "ruff", "format", "--check", "."], check=True)
    subprocess.run(["poetry", "run", "mypy", "app/"], check=True)


@app.command()
def migrate(message: str | None = typer.Option(None, "--message", "-m")) -> None:
    """Run database migrations or create a new one."""
    if message:
        subprocess.run(
            ["poetry", "run", "alembic", "revision", "--autogenerate", "-m", message],
            check=True,
        )
    else:
        subprocess.run(["poetry", "run", "alembic", "upgrade", "head"], check=True)


@app.command()
def seed() -> None:
    """Seed the database."""
    subprocess.run(["poetry", "run", "python", "scripts/seed.py"], check=True)


@app.command()
def docker(
    up: bool = typer.Option(True, "--up/--down"),
    full: bool = typer.Option(False, "--full/--core"),
) -> None:
    """Manage Docker services.

    --core (default): db, redis, adminer, redis-commander only.
    --full: includes monitoring stack (loki, tempo, promtail, minio).
    """
    if up:
        cmd = ["docker", "compose", "-f", "docker-compose.dev.yml", "up", "-d"]
        if full:
            cmd = [
                "docker", "compose", "-f", "docker-compose.dev.yml",
                "--profile", "monitoring", "up", "-d",
            ]
        subprocess.run(cmd, check=True)
    else:
        cmd = ["docker", "compose", "-f", "docker-compose.dev.yml", "down"]
        if full:
            cmd = [
                "docker", "compose", "-f", "docker-compose.dev.yml",
                "--profile", "monitoring", "down",
            ]
        subprocess.run(cmd, check=True)


@app.command()
def setup_fast() -> None:
    """Fast setup: start core services only, run migrations, verify."""
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.dev.yml", "up", "-d", "db", "redis"],
        check=True,
    )
    typer.echo("Waiting for services to become healthy...")
    subprocess.run(
        ["docker", "compose", "-f", "docker-compose.dev.yml", "up", "-d", "db", "redis"],
        check=True,
    )
    subprocess.run(["poetry", "install"], check=True)
    subprocess.run(["poetry", "run", "alembic", "upgrade", "head"], check=True)
    typer.echo("Setup complete. Run `poetry run python app/cli.py dev` to start.")


@app.command()
def celery(hot_reload: bool = typer.Option(True, "--hot-reload/--no-hot-reload")) -> None:
    """Start the Celery worker with optional hot-reload via watchdog.

    --hot-reload (default): auto-restarts worker on Python file changes.
    --no-hot-reload: plain celery worker.
    """
    if hot_reload:
        subprocess.run(
            [
                "poetry", "run", "watchmedo", "auto-restart",
                "--directory=app",
                "--pattern=*.py",
                "--recursive",
                "--",
                "celery", "-A", "app.core.celery_app",
                "worker", "--loglevel=info",
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                "poetry", "run", "celery",
                "-A", "app.core.celery_app",
                "worker", "--loglevel=info",
            ],
            check=True,
        )


@app.command()
def graphql() -> None:
    """Open the GraphQL playground in the browser."""
    url = "http://localhost:8000/graphql"
    typer.launch(url)


@app.command()
def load_test() -> None:
    """Run Locust load tests."""
    subprocess.run(["poetry", "run", "locust", "-f", "locustfile.py"], check=True)


@app.command()
def profile() -> None:
    """Profile the application."""
    subprocess.run(
        [
            "py-spy",
            "record",
            "-o",
            "profile.svg",
            "--",
            "poetry",
            "run",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",  # nosec B104
            "--port",
            "8000",
        ],
        check=True,
    )


@app.command()
def scaffold() -> None:
    """Interactive scaffolding tool."""
    subprocess.run(["poetry", "run", "python", "scripts/scaffold.py"], check=True)


@app.command()
def anonymise_db() -> None:
    """Anonymise the local database."""
    subprocess.run(["poetry", "run", "python", "scripts/anonymise_db.py"], check=True)


@app.command()
def verify_env() -> None:
    """Verify all required services are running."""
    subprocess.run(["poetry", "run", "python", "scripts/verify_env.py"], check=True)


@app.command()
def setup() -> None:
    """Complete project setup (install + migrate)."""
    install()
    migrate()


if __name__ == "__main__":
    app()
