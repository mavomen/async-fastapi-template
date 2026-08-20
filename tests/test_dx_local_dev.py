"""Tests for DX improvements: compose profiles, CLI commands, Jinja2 reload."""

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()

COMPOSE_FILE = Path("docker-compose.dev.yml")


class TestComposeDevProfiles:
    def test_dev_compose_has_core_services(self):
        """Core services (db, redis) should have no profiles (always start)."""
        import yaml

        with COMPOSE_FILE.open() as f:
            config = yaml.safe_load(f)

        assert "db" in config["services"]
        assert "redis" in config["services"]
        assert "db_replica" in config["services"]
        assert "adminer" in config["services"]
        assert "redis-commander" in config["services"]

        for svc in ("db", "redis", "db_replica", "adminer", "redis-commander"):
            assert "profiles" not in config["services"][svc], f"{svc} should not have profiles"

    def test_dev_compose_monitoring_has_profiles(self):
        """Monitoring services should be gated behind the 'monitoring' profile."""
        import yaml

        with COMPOSE_FILE.open() as f:
            config = yaml.safe_load(f)

        for svc in ("loki", "tempo", "promtail", "minio", "minio-init"):
            assert svc in config["services"], f"{svc} not found"
            assert config["services"][svc].get("profiles") == ["monitoring"], (
                f"{svc} should have profiles: [monitoring]"
            )

    def test_dev_compose_core_healthchecks(self):
        """db and redis should have healthchecks for fast startup."""
        import yaml

        with COMPOSE_FILE.open() as f:
            config = yaml.safe_load(f)

        assert "healthcheck" in config["services"]["db"]
        assert "healthcheck" in config["services"]["redis"]

    def test_dev_compose_depends_on_healthy(self):
        """adminer and redis-commander should use service_healthy condition."""
        import yaml

        with COMPOSE_FILE.open() as f:
            config = yaml.safe_load(f)

        adminer_deps = config["services"]["adminer"]["depends_on"]
        assert adminer_deps["db"]["condition"] == "service_healthy"

        rc_deps = config["services"]["redis-commander"]["depends_on"]
        assert rc_deps["redis"]["condition"] == "service_healthy"


class TestCLICommands:
    def test_setup_fast_exists(self):
        result = runner.invoke(app, ["setup-fast", "--help"])
        assert result.exit_code == 0
        assert "setup" in result.output.lower()

    def test_docker_core_full_flag(self):
        result = runner.invoke(app, ["docker", "--help"])
        assert result.exit_code == 0
        assert "--core" in result.output or "--full" in result.output

    def test_celery_hot_reload_flag(self):
        result = runner.invoke(app, ["celery", "--help"])
        assert result.exit_code == 0
        assert "--hot-reload" in result.output


class TestJinja2AutoReload:
    def test_admin_auto_reload_in_dev(self):
        """Admin Jinja env should have auto_reload=True when ENVIRONMENT=development."""
        import importlib

        import app.admin as admin_mod

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            importlib.reload(admin_mod)
            assert admin_mod.env.auto_reload is True

    def test_admin_auto_reload_not_in_prod(self):
        """Admin Jinja env should have auto_reload=False in production."""
        import importlib

        import app.admin as admin_mod

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
            importlib.reload(admin_mod)
            assert admin_mod.env.auto_reload is False
