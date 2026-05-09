"""Tests for CLI command structure (no execution)."""

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_app_help():
    """CLI app help includes available commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.output


def test_dev_command_exists():
    """The dev command is registered."""
    result = runner.invoke(app, ["dev", "--help"])
    assert result.exit_code == 0


def test_test_command_exists():
    """The test command is registered (does not execute tests)."""
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
