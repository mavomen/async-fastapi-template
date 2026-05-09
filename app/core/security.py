from datetime import UTC, datetime, timedelta
from typing import Any

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


def _generate_keys():
    global _jwks_private_key, _jwks_public_key  # noqa: PLW0603
    if _jwks_private_key is None:
        _jwks_private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        _jwks_public_key = _jwks_private_key.public_key()


def sign_with_rs256(payload: dict) -> str:
    _generate_keys()
    return jwt.encode(payload, _jwks_private_key, algorithm="RS256")


def decode_with_rs256(token: str) -> dict:
    _generate_keys()
    return jwt.decode(token, _jwks_public_key, algorithms=["RS256"])


def get_jwks() -> dict:
    import json

    from jose import jwk as jose_jwk

    _generate_keys()
    key_dict = json.loads(jose_jwk.construct(_jwks_public_key, algorithm="RS256"))
    return {"keys": [key_dict]}


# -------- password hashing --------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = plain_password.encode("utf-8")
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    plain_bytes = password.encode("utf-8")
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


# -------- JWT token creation / validation --------
def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}

    if settings.ALGORITHM == "RS256":
        return sign_with_rs256(to_encode)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        if settings.ALGORITHM == "RS256":
            return decode_with_rs256(token)
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
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


# -------- email verification tokens --------
def create_verification_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(hours=24)
    to_encode = {"exp": expire, "sub": str(user_id), "purpose": "email_verify"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_verification_token(token: str) -> dict:
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
    return payload
