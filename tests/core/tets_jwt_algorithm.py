"""Regression test for JWT algorithm."""

import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


@pytest.mark.skipif(settings.ALGORITHM != "RS256", reason="RS256 not enabled")
def test_rs256_token_roundtrip():
    token = create_access_token(subject="test")
    payload = decode_access_token(token)
    assert payload["sub"] == "test"
