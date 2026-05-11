"""Tests for refresh token edge cases."""

import pytest
from unittest.mock import patch
from app.core.config import settings
from app.core.security import create_refresh_token, decode_refresh_token


def test_decode_refresh_token_invalid_purpose():
    """Token with wrong purpose raises 401."""
    from fastapi import HTTPException
    from jose import jwt
    from datetime import UTC, datetime, timedelta

    token = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(days=1), "purpose": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_refresh_token(token)
    assert exc.value.status_code == 401


def test_refresh_token_roundtrip():
    """Refresh token can be created and decoded."""
    token = create_refresh_token(subject=42)
    payload = decode_refresh_token(token)
    assert payload["sub"] == "42"
    assert payload["purpose"] == "refresh"
