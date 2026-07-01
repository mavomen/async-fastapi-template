"""CRUD operations for API keys."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key, verify_api_key
from app.crud.base import CRUDBase
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate


class CRUDApiKey(CRUDBase[ApiKey, ApiKeyCreate, ApiKeyUpdate]):
    async def create_with_raw_key(
        self, db: AsyncSession, *, user_id: int, obj_in: ApiKeyCreate
    ) -> tuple[ApiKey, str]:
        raw_key, hashed_key, prefix = generate_api_key()
        scopes = obj_in.scopes or None
        db_obj = ApiKey(
            user_id=user_id,
            name=obj_in.name,
            key_prefix=prefix,
            hashed_key=hashed_key,
            scopes=scopes,
            expires_at=obj_in.expires_at,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj, raw_key

    async def get_by_prefix(self, db: AsyncSession, *, prefix: str) -> ApiKey | None:
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, db: AsyncSession, *, user_id: int) -> list[ApiKey]:
        result = await db.execute(
            select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def verify(self, db: AsyncSession, *, raw_key: str) -> ApiKey | None:
        prefix = raw_key[:10]
        api_key = await self.get_by_prefix(db, prefix=prefix)
        if api_key is None:
            return None
        if not verify_api_key(raw_key, api_key.hashed_key):
            return None
        now = datetime.now(UTC)
        if not api_key.is_active:
            return None
        if api_key.expires_at and api_key.expires_at < now:
            return None
        await db.execute(update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=now))
        await db.commit()
        return api_key


api_key = CRUDApiKey(ApiKey)
