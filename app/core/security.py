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


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> User | None:
    from datetime import UTC, datetime

    from app.core.config import settings
    from app.crud.user import user as crud_user
    from app.services.auth_audit import log_auth_event

    user = await crud_user.get_by_email(db, email=email)
    if not user:
        await log_auth_event(
            db,
            event_type="login_failure",
            ip_address=ip_address,
            user_agent=user_agent,
            details={"email": email, "reason": "user_not_found"},
        )
        return None

    now = datetime.now(UTC).replace(tzinfo=None)

    # Check if account is locked
    if user.locked_until and user.locked_until > now:
        await log_auth_event(
            db,
            event_type="account_locked",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"locked_until": user.locked_until.isoformat()},
        )
        from app.core.exceptions import LockedOutException

        raise LockedOutException(
            detail=f"Account locked until {user.locked_until.isoformat()}. Try again later."
        )

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        was_locked = False
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            was_locked = True
        db.add(user)
        await db.commit()

        details: dict[str, object] = {
            "failed_attempts": user.failed_login_attempts,
            "max_attempts": settings.MAX_LOGIN_ATTEMPTS,
        }
        event_type = "account_locked" if was_locked else "login_failure"
        if was_locked and user.locked_until:
            details["locked_until"] = user.locked_until.isoformat()
        await log_auth_event(
            db,
            event_type=event_type,
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.add(user)
    await db.commit()

    await log_auth_event(
        db,
        event_type="login_success",
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
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


# -------- magic link tokens --------
def create_magic_link_token(email: str) -> str:
    """Create a short-lived signed token for passwordless login."""
    to_encode = _make_jwt_payload(email, timedelta(minutes=settings.MAGIC_LINK_EXPIRE_MINUTES), purpose="magic_link")
    if settings.ALGORITHM == "RS256":
        return sign_with_rs256(to_encode)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)  # type: ignore[no-any-return]


def decode_magic_link_token(token: str) -> dict[str, Any]:
    """Validate a magic link token and return its payload."""
    try:
        if settings.ALGORITHM == "RS256":
            return decode_with_rs256(token)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired magic link",
        )
    if payload.get("purpose") != "magic_link":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token purpose",
        )
    return payload  # type: ignore[no-any-return]


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
