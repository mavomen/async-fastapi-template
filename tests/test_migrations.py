"""Migration smoke tests — verify Alembic migrations apply cleanly."""

import subprocess

import pytest


@pytest.mark.slow
class TestMigrations:
    def test_upgrade_head(self):
        """Run alembic upgrade head and verify it completes."""
        result = subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"alembic upgrade failed:\n{result.stderr}"

    def test_downgrade_and_reupgrade(self):
        """Downgrade one revision and re-upgrade to verify idempotency."""
        # Downgrade one step
        result = subprocess.run(
            ["poetry", "run", "alembic", "downgrade", "-1"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"alembic downgrade failed:\n{result.stderr}"

        # Re-upgrade to head
        result = subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"alembic re-upgrade failed:\n{result.stderr}"

    def test_current_revision(self):
        """Verify alembic current reports a revision (DB is migrated)."""
        result = subprocess.run(
            ["poetry", "run", "alembic", "current"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0
        assert "(head)" in result.stdout or len(result.stdout.strip()) > 0, (
            "Expected at least one revision in alembic current output"
        )

    def test_migrations_are_idempotent(self):
        """Running upgrade head twice in succession should not fail."""
        for _ in range(2):
            result = subprocess.run(
                ["poetry", "run", "alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            assert result.returncode == 0, f"Second alembic upgrade failed:\n{result.stderr}"
