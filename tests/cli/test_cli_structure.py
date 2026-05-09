"""Tests for CLI command registration."""

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_help_output():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.output


def test_dev_help():
    result = runner.invoke(app, ["dev", "--help"])
    assert result.exit_code == 0


def test_test_help():
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0


def test_migrate_help():
    result = runner.invoke(app, ["migrate", "--help"])
    assert result.exit_code == 0


def test_lint_help():
    result = runner.invoke(app, ["lint", "--help"])
    assert result.exit_code == 0


def test_docker_help():
    result = runner.invoke(app, ["docker", "--help"])
    assert result.exit_code == 0


def test_scaffold_help():
    result = runner.invoke(app, ["scaffold", "--help"])
    assert result.exit_code == 0
