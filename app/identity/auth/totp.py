"""TOTP (Time-based One-Time Password) utilities for 2FA."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def generate_totp_secret() -> str:
    """Generate a random base32-encoded TOTP secret."""
    return secrets.token_hex(20).upper()


def get_totp_uri(secret: str, email: str) -> str:
    """Generate an otpauth:// URI for QR code provisioning."""
    import pyotp

    return pyotp.totp.TOTP(
        secret,
        interval=settings.TOTP_CODE_EXPIRE_SECONDS,
        digits=settings.TOTP_CODE_LENGTH,
    ).provisioning_uri(name=email, issuer_name=settings.TOTP_ISSUER_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret. Allows a small time skew."""
    import pyotp

    totp = pyotp.TOTP(
        secret,
        interval=settings.TOTP_CODE_EXPIRE_SECONDS,
        digits=settings.TOTP_CODE_LENGTH,
    )
    return totp.verify(code, valid_window=1)


def generate_backup_codes() -> list[str]:
    """Generate a list of one-time backup codes (unhashed)."""
    codes: list[str] = []
    for _ in range(settings.TOTP_BACKUP_CODE_COUNT):
        code = secrets.token_hex(5).upper()
        codes.append(code)
    return codes


def hash_backup_code(code: str) -> str:
    """SHA-256 hash a backup code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def verify_backup_code(code: str, hashed_codes: str | None) -> str | None:
    """Check a backup code against stored hashed codes.

    If valid, returns the hash so it can be removed.
    """
    if not hashed_codes:
        return None
    stored_hashes = [h.strip() for h in hashed_codes.split(",") if h.strip()]
    code_hash = hash_backup_code(code)
    for stored in stored_hashes:
        if hmac.compare_digest(code_hash, stored):
            return stored
    return None


def remove_used_backup_code(used_hash: str, stored_codes: str | None) -> str | None:
    """Remove a used backup code from the comma-separated list."""
    if not stored_codes:
        return None
    remaining = [h.strip() for h in stored_codes.split(",") if h.strip() and h.strip() != used_hash]
    return ",".join(remaining) if remaining else None


def create_totp_challenge_token(user_id: int) -> str:
    """Create a short-lived JWT that proves the user passed password auth."""
    now = datetime.now(UTC)
    expire = now + timedelta(seconds=settings.TOTP_CHALLENGE_EXPIRE_SECONDS)
    payload = {
        "sub": str(user_id),
        "purpose": "totp_challenge",
        "iat": int(now.timestamp()),
        "exp": expire,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore[no-any-return]


def decode_totp_challenge_token(token: str) -> dict[str, Any]:
    """Validate and return a TOTP challenge token payload."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired challenge token",
        )
    if payload.get("purpose") != "totp_challenge":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token purpose",
        )
    return payload  # type: ignore[no-any-return]
