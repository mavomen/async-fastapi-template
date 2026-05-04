from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a bcrypt hashed password.
    Handles passwords longer than 72 bytes by truncating (silently).
    """
    plain_bytes = plain_password.encode("utf-8")
    # Truncate to 72 bytes, bcrypt's maximum
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


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """
    Generates a JWT access token.

    :param subject: The subject of the token (e.g., user ID or email).
    :param expires_delta: The lifespan of the token.
    :return: The encoded JWT token.
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
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
    from app.crud.user import user as crud_user  # lazy import breaks circular dependency

    user = await crud_user.get_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
