from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import RedisCache
from app.core.cache import cache as redis_cache
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.crud.user import user as crud_user
from app.models.user import User
from app.services.email import EmailService, email_service
from app.storage.base import StorageBackend
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency to retrieve the current authenticated user from a JWT,
    with roles and permissions eagerly loaded for permission checks.
    """
    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: subject missing",
        )
    # Fetch user with roles and permissions loaded
    user = await crud_user.get_with_roles(db, id=int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    return user


async def get_cache() -> RedisCache:
    """FastAPI dependency for Redis cache."""
    return redis_cache


async def get_storage() -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        return S3Storage()
    return LocalStorage()


async def get_email_service() -> EmailService:
    """FastAPI dependency for email service."""
    return email_service


async def get_gql_context(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Build GraphQL context with database session and optional authenticated user.
    """
    current_user = None
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        from app.core.security import decode_access_token
        from app.crud.user import user as crud_user

        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                current_user = await crud_user.get(db, id=int(user_id))
        except Exception:
            pass  # token invalid or expired – resolvers can still check permissions
    return {"request": request, "db": db, "current_user": current_user}


async def get_current_tenant_id() -> int | None:
    """FastAPI dependency that returns the current tenant ID."""
    from app.core.tenant import get_current_tenant

    return get_current_tenant()
