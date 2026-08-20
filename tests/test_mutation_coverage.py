"""Tests for mutation testing and migration infrastructure."""

import tomllib
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()

PYPROJECT = Path("pyproject.toml")


class TestMutmutConfig:
    def test_mutmut_in_dev_dependencies(self):
        """mutmut should be declared as a dev dependency."""
        with PYPROJECT.open("rb") as f:
            config = tomllib.load(f)
        dev_deps = config["tool"]["poetry"]["group"]["dev"]["dependencies"]
        assert "mutmut" in dev_deps

    def test_mutmut_section_exists(self):
        """pyproject.toml should have a [tool.mutmut] section."""
        with PYPROJECT.open("rb") as f:
            config = tomllib.load(f)
        assert "mutmut" in config.get("tool", {})

    def test_mutmut_paths_to_mutate(self):
        """mutmut should target app/ directory."""
        with PYPROJECT.open("rb") as f:
            config = tomllib.load(f)
        mutmut = config["tool"]["mutmut"]
        assert "app/" in mutmut["paths_to_mutate"]

    def test_mutation_workflow_targets_full_app(self):
        """mutation.yml should NOT have hardcoded file list."""
        workflow = Path(".github/workflows/mutation.yml").read_text()
        assert "app/core/security.py" not in workflow
        assert "--paths-to-mutate" not in workflow or "app/" in workflow


class TestMigrationWorkflow:
    def test_migration_smoke_test_exists(self):
        """tests/test_migrations.py should exist."""
        assert Path("tests/test_migrations.py").exists()

    def test_migration_test_has_slow_marker(self):
        """Migration tests should be marked as slow."""
        from tests.test_migrations import TestMigrations

        markers = getattr(TestMigrations, "pytestmark", [])
        marker_names = [m.args[0] if m.args else m.name for m in markers]
        assert "slow" in marker_names


class TestCLI:
    def test_mutation_command_exists(self):
        result = runner.invoke(app, ["mutation", "--help"])
        assert result.exit_code == 0
        assert "mutmut" in result.output.lower() or "mutation" in result.output.lower()

    def test_mutation_command_accepts_paths(self):
        result = runner.invoke(app, ["mutation", "--help"])
        assert result.exit_code == 0
        assert "--paths" in result.output
