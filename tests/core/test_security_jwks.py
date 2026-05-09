"""Tests for RS256 JWT and JWKS functions."""

from app.core.security import decode_with_rs256, get_jwks, sign_with_rs256


def test_rs256_roundtrip():
    token = sign_with_rs256({"sub": "42"})
    payload = decode_with_rs256(token)
    assert payload["sub"] == "42"


def test_jwks_contains_keys():
    jwks = get_jwks()
    assert "keys" in jwks
    assert len(jwks["keys"]) >= 1
