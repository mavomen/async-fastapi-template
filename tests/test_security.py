"""
Tests for security utilities: password hashing, JWT creation, and decoding.
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_valid_bcrypt(self):
        password = "StrongP4$$word!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        password = "mysecret"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "correct"
        wrong_password = "different"
        hashed = get_password_hash(password)
        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_against_different_hash(self):
        """Hashed password of one user shouldn't match another plaintext."""
        hashed1 = get_password_hash("alpha")
        hashed2 = get_password_hash("beta")
        assert verify_password("alpha", hashed2) is False
        assert verify_password("beta", hashed1) is False

    def test_hash_same_password_different_salts(self):
        password = "salted"
        hashed1 = get_password_hash(password)
        hashed2 = get_password_hash(password)
        # They should be different because of random salts
        assert hashed1 != hashed2
        # But both should verify against the original password
        assert verify_password(password, hashed1)
        assert verify_password(password, hashed2)


class TestJWT:
    def test_create_access_token_returns_string(self):
        token = create_access_token(subject="test_user")
        assert isinstance(token, str)
        parts = token.split(".")
        assert len(parts) == 3  # Header, payload, signature

    def test_create_access_token_with_expiry(self):
        token = create_access_token(
            subject="user", expires_delta=timedelta(minutes=5)
        )
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "user"
        assert "exp" in payload

    def test_create_access_token_default_expiry(self):
        token = create_access_token(subject="default_exp")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Expiry should be roughly ACCESS_TOKEN_EXPIRE_MINUTES from now
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], timezone.utc)
        expected = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Allow a few seconds of skew
        assert abs((exp - expected).total_seconds()) < 5

    def test_decode_access_token_valid(self):
        token = create_access_token(subject="decode_me")
        payload = decode_access_token(token)
        assert payload["sub"] == "decode_me"
        assert "exp" in payload

    def test_decode_access_token_invalid(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid.token.string")
        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    def test_decode_access_token_expired(self):
        # Create token that expired 1 minute ago
        token = create_access_token(
            subject="expired", expires_delta=timedelta(minutes=-1)
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401
