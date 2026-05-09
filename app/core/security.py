from datetime import UTC, datetime, timedelta
from typing import Any, Union

import bcrypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

_jwks_private_key = None
_jwks_public_key = None


def _get_rsa_private_key():
    global _jwks_private_key, _jwks_public_key
    if _jwks_private_key is None:
        _jwks_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        _jwks_public_key = _jwks_private_key.public_key()
    return _jwks_private_key


def _get_rsa_public_key():
    _get_rsa_private_key()
    return _jwks_public_key


def sign_with_rs256(payload: dict) -> str:
    """Sign a JWT payload using RS256."""
    private_key = _get_rsa_private_key()
    return jwt.encode(payload, private_key, algorithm="RS256")


def decode_with_rs256(token: str) -> dict:
    """Decode and validate an RS256 JWT."""
    public_key = _get_rsa_public_key()
    return jwt.decode(token, public_key, algorithms=["RS256"])


def get_jwks() -> dict:
    """Return a JWKS response containing the RSA public key."""
    import json

    from jose import jwk as jose_jwk

    public_key = _get_rsa_public_key()
    key_dict = json.loads(jose_jwk.construct(public_key, algorithm="RS256"))
    return {"keys": [key_dict]}


# ----- existing functions (unchanged except token functions now respect ALGORITHM) -----


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hashed password.
    Handles passwords longer than 72 bytes by truncating (silently).
    """
    plain_bytes = plain_password.encode("utf-8")
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password with bcrypt, truncating if longer than 72 bytes.
    """
    plain_bytes = password.encode("utf-8")
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta | None = None
) -> str:
    """
    Generates a JWT access token.
    Uses RS256 if settings.ALGORITHM == "RS256", otherwise HS256 by default.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}

    if settings.ALGORITHM == "RS256":
        return sign_with_rs256(to_encode)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Args:
        token: The JWT string.

    Returns:
        The decoded payload as a dictionary.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        if settings.ALGORITHM == "RS256":
            return decode_with_rs256(token)
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Authenticates a user.

    Args:
        db: The database session (AsyncSession).
        email: The user's email.
        password: The user's plain-text password.

    Returns:
        The authenticated user object or None if authentication fails.
    """
    from app.crud.user import \
        user as crud_user  # lazy import breaks circular dependency

    user = await crud_user.get_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_verification_token(user_id: int) -> str:
    """Create a short-lived token for email verification."""
    expire = datetime.now(UTC) + timedelta(hours=24)
    to_encode = {"exp": expire, "sub": str(user_id), "purpose": "email_verify"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_verification_token(token: str) -> dict:
    """Decode and validate an email verification token."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("purpose") != "email_verify":
            raise ValueError("Invalid token purpose")
        return payload
    except (JWTError, ValueError):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
