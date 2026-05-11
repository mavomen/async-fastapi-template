"""Test refresh token creation and decoding."""

from app.core.security import create_refresh_token, decode_refresh_token


def test_create_refresh_token_returns_string():
    token = create_refresh_token(subject=42)
    assert isinstance(token, str)
    assert token.count(".") == 2


def test_decode_invalid_refresh_token():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        decode_refresh_token("invalid.token.here")
