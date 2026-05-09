"""CI Smoke test - verifies the environment boots correctly."""

import platform
import sys


def test_python_version():
    """Check that Python version is at least 3.12."""
    version = sys.version_info
    assert version.major == 3 and version.minor >= 12, f"Unexpected Python version: {version}"


def test_platform():
    """Ensure we are on Linux in CI."""
    assert "linux" in platform.system().lower(), f"Unexpected platform: {platform.system()}"
