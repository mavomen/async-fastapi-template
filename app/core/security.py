from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

# -------- RS256 key management --------
_jwks_private_key = None
_jwks_public_key = None


def _generate_keys() -> None:
    global _jwks_private_key, _jwks_public_key  # noqa: PLW0603
    if _jwks_private_key is None:
        _jwks_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        _jwks_public_key = _jwks_private_key.public_key()


def sign_with_rs256(payload: dict[str, Any]) -> str:
    _generate_keys()
    return jwt.encode(payload, _jwks_private_key, algorithm="RS256")  # type: ignore[no-any-return]


def decode_with_rs256(token: str) -> dict[str, Any]:
    _generate_keys()
    return jwt.decode(token, _jwks_public_key, algorithms=["RS256"])  # type: ignore[no-any-return]


def get_jwks() -> dict[str, Any]:
    _generate_keys()
    from jose import jwk as jose_jwk

    key = jose_jwk.construct(_jwks_public_key, algorithm="RS256")
    key_dict = key.to_dict()  # JWK object -> dict
    return {"keys": [key_dict]}


# -------- password hashing --------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hashed password.
    **Important:** Passwords longer than 72 bytes are silently truncated to the first 72 bytes.
    This is a limitation of bcrypt, not this implementation.
    """
    plain_bytes = plain_password.encode("utf-8")
    if len(plain_bytes) > 72:
        import logging

        logger = logging.getLogger("app.security")
        logger.debug("Password truncated to 72 bytes for bcrypt")
        plain_bytes = plain_bytes[:72]
    return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password with bcrypt.
    **Important:** Passwords longer than 72 bytes are silently truncated to the first 72 bytes.
    """
    plain_bytes = password.encode("utf-8")
    if len(plain_bytes) > 72:
        import logging

        logger = logging.getLogger("app.security")
        logger.debug("Password truncated to 72 bytes for bcrypt")
        plain_bytes = plain_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


# -------- JWT token creation / validation --------
def _make_jwt_payload(subject: str | Any, expires_delta: timedelta | None, purpose: str | None = None) -> dict[str, Any]:
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "jti": str(uuid4()),
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    if purpose:
        payload["purpose"] = purpose
    return payload


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    to_encode = _make_jwt_payload(subject, expires_delta)

    if settings.ALGORITHM == "RS256":
        return sign_with_rs256(to_encode)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore[no-any-return]


# -------- access token validation --------
def decode_access_token(token: str) -> dict[str, Any]:
    try:
        if settings.ALGORITHM == "RS256":
            return decode_with_rs256(token)
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])  # type: ignore[no-any-return]
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    from app.crud.user import user as crud_user

    user = await crud_user.get_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# -------- refresh token --------
def create_refresh_token(subject: str | Any) -> str:
    """Create a long-lived refresh token."""
    to_encode = _make_jwt_payload(subject, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), purpose="refresh")
    if settings.ALGORITHM == "RS256":
        return sign_with_rs256(to_encode)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore[no-any-return]


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Validate a refresh token and return its payload."""
    try:
        if settings.ALGORITHM == "RS256":
            return decode_with_rs256(token)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "refresh":
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token purpose"
            )
        return payload  # type: ignore[no-any-return]
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# -------- email verification tokens --------
def create_verification_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(hours=24)
    to_encode = {"exp": expire, "sub": str(user_id), "purpose": "email_verify"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore[no-any-return]


def decode_verification_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    if payload.get("purpose") != "email_verify":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token purpose",
        )
    return payload  # type: ignore[no-any-return]
