"""Tests that all CLI commands are registered and print help."""

import pytest
from typer.testing import CliRunner
from app.cli import app

runner = CliRunner()

commands = [
    "install", "dev", "test", "lint", "migrate", "seed",
    "docker", "celery", "graphql", "load-test", "profile",
    "scaffold", "anonymise-db", "verify-env", "setup",
]

@pytest.mark.parametrize("command", commands)
def test_command_help(command):
    result = runner.invoke(app, [command, "--help"])
    assert result.exit_code == 0
