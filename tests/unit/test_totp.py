"""Tests for TOTP utility functions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth.totp import (
    create_totp_challenge_token,
    decode_totp_challenge_token,
    generate_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_code,
    remove_used_backup_code,
    verify_backup_code,
    verify_totp_code,
)
from app.core.config import settings


class TestGenerateSecret:
    def test_generates_hex_string(self):
        secret = generate_totp_secret()
        assert len(secret) == 40
        assert all(c in "0123456789ABCDEF" for c in secret)

    def test_generates_unique_secrets(self):
        secrets = {generate_totp_secret() for _ in range(100)}
        assert len(secrets) == 100


class TestGetTOTPUri:
    def test_uri_contains_correct_parts(self):
        secret = generate_totp_secret()
        uri = get_totp_uri(secret, "test@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "test%40example.com" in uri
        assert "secret=" in uri
        assert settings.TOTP_ISSUER_NAME in unquote(uri)

    def test_uri_uses_email_as_name(self):
        uri = get_totp_uri("AAAAAAAAAAAAAAAAAAAAAA", "user@test.com")
        assert "user%40test.com" in uri


class TestVerifyTOTPCode:
    def test_verify_valid_code(self):
        import pyotp

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret, interval=30, digits=6)
        code = totp.now()
        assert verify_totp_code(secret, code) is True

    def test_verify_invalid_code(self):
        import pyotp

        secret = pyotp.random_base32()
        assert verify_totp_code(secret, "000000") is False

    def test_verify_empty_code(self):
        import pyotp

        secret = pyotp.random_base32()
        assert verify_totp_code(secret, "") is False


class TestBackupCodes:
    def test_generates_correct_count(self):
        codes = generate_backup_codes()
        assert len(codes) == settings.TOTP_BACKUP_CODE_COUNT
        assert len(set(codes)) == len(codes)

    def test_codes_are_uppercase_hex(self):
        codes = generate_backup_codes()
        for code in codes:
            assert len(code) == 10
            assert all(c in "0123456789ABCDEF" for c in code)

    def test_hash_and_verify(self):
        codes = generate_backup_codes()
        hashed = ",".join(hash_backup_code(c) for c in codes)
        for code in codes:
            result = verify_backup_code(code, hashed)
            assert result == hash_backup_code(code)

    def test_verify_wrong_code_returns_none(self):
        codes = generate_backup_codes()
        hashed = ",".join(hash_backup_code(c) for c in codes)
        assert verify_backup_code("WRONG", hashed) is None

    def test_verify_empty_storage_returns_none(self):
        assert verify_backup_code("SOME", None) is None
        assert verify_backup_code("SOME", "") is None

    def test_remove_used_code(self):
        codes = generate_backup_codes()
        hashed = ",".join(hash_backup_code(c) for c in codes)
        used_hash = hash_backup_code(codes[0])
        remaining = remove_used_backup_code(used_hash, hashed)
        assert used_hash not in remaining
        assert len(remaining.split(",")) == len(codes) - 1

    def test_remove_from_empty_returns_none(self):
        assert remove_used_backup_code("hash", None) is None
        assert remove_used_backup_code("hash", "") is None


class TestTOTPChallengeToken:
    def test_create_and_decode(self):
        token = create_totp_challenge_token(user_id=42)
        payload = decode_totp_challenge_token(token)
        assert payload["sub"] == "42"
        assert payload["purpose"] == "totp_challenge"
        assert "jti" in payload
        assert "exp" in payload

    def test_expired_token_raises(self):
        payload = {
            "sub": "1",
            "purpose": "totp_challenge",
            "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(minutes=5)).timestamp()),
            "jti": "test",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException):
            decode_totp_challenge_token(token)

    def test_wrong_purpose_raises(self):
        token = create_totp_challenge_token(user_id=1)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        payload["purpose"] = "login"
        tampered = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(HTTPException):
            decode_totp_challenge_token(tampered)
