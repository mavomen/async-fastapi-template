"""Tests for infrastructure configuration files."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_grafana_datasource_dir_exists():
    datasource_file = PROJECT_ROOT / "monitoring" / "grafana" / "datasources" / "datasource.yml"
    assert datasource_file.is_file(), f"Expected datasource file at {datasource_file}"

    content = datasource_file.read_text()
    assert "datasource" in content.lower() or "prometheus" in content.lower()


def test_grafana_dashboard_dir_exists():
    dashboard_dir = PROJECT_ROOT / "monitoring" / "grafana" / "dashboards"
    assert dashboard_dir.is_dir()
    assert len(list(dashboard_dir.glob("*.json"))) >= 1


def test_dockerfile_useradd_before_copy():
    dockerfile = PROJECT_ROOT / "Dockerfile"
    content = dockerfile.read_text()

    useradd_line = None
    copy_line = None
    for i, line in enumerate(content.splitlines(), 1):
        if "useradd" in line:
            useradd_line = i
        if line.strip().startswith("COPY"):
            copy_line = i

    assert useradd_line is not None, "Dockerfile missing RUN useradd"
    assert copy_line is not None, "Dockerfile missing COPY . ."
    assert useradd_line < copy_line, (
        f"RUN useradd at line {useradd_line} should come before COPY at line {copy_line}"
    )


def test_dockerfile_has_healthcheck():
    dockerfile = PROJECT_ROOT / "Dockerfile"
    assert "HEALTHCHECK" in dockerfile.read_text()


def test_production_compose_no_internal_ports():
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    compose = yaml.safe_load(compose_file.read_text())

    internal_services = {"db", "redis", "prometheus", "grafana"}
    for name, service in compose.get("services", {}).items():
        if name in internal_services:
            ports = service.get("ports", [])
            for port in ports:
                assert str(port).startswith("#"), (
                    f"Service '{name}' has uncommented host port mapping: {port}. "
                    "Internal services should not expose ports to host in production."
                )


def test_production_compose_app_port_exposed():
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    compose = yaml.safe_load(compose_file.read_text())

    app = compose["services"].get("app", {})
    ports = app.get("ports", [])
    assert len(ports) >= 1, "App service must expose at least one port"


def test_search_migration_uses_create_index():

    migrations_dir = PROJECT_ROOT / "alembic" / "versions"
    target = None
    for f in migrations_dir.iterdir():
        if "005_add_search_and_audit" in f.name:
            target = f
            break

    assert target is not None, "Migration 005_add_search_and_audit not found"
    content = target.read_text()

    assert "op.create_index" in content, (
        "Migration should use op.create_index instead of raw CREATE INDEX"
    )
    assert 'postgresql_using="gin"' in content, "Index should specify postgresql_using='gin'"


def test_celery_app_has_single_init():
    celery_app_file = PROJECT_ROOT / "app" / "core" / "celery_app.py"
    content = celery_app_file.read_text()

    count = content.count("celery_app = Celery(")
    assert count == 1, f"Expected 1 Celery() init, found {count}. Remove dead first init."
