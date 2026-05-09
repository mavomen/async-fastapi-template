"""Regression test for VERSION string."""

from app.core.config import settings


def test_version_is_3_0_0():
    assert settings.VERSION == "3.0.0"
