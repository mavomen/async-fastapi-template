"""Test config validation edge cases."""

import pytest

from app.core.config import Settings


def test_validate_environment_valid():
    settings = Settings(ENVIRONMENT="production", SECRET_KEY="a" * 32)
    assert settings.ENVIRONMENT == "production"


def test_validate_environment_invalid():
    with pytest.raises(Exception):
        Settings(ENVIRONMENT="invalid", SECRET_KEY="a" * 32)
