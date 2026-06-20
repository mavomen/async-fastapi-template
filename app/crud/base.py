"""Base CRUD class with common async database operations."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> ModelType | None:
        result = await db.execute(select(self.model).where(self.model.id == id))  # type: ignore[attr-defined]
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        result = await db.execute(
            select(self.model).order_by(self.model.id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    async def get_multi_cursor(
        self,
        db: AsyncSession,
        *,
        cursor: int | None = None,
        limit: int = 50,
    ) -> tuple[list[ModelType], int | None]:
        """Keyset (cursor) pagination — WHERE id > cursor ORDER BY id LIMIT limit+1.

        Returns (items, next_cursor) where next_cursor is the last id to
        pass back as the cursor on the next request.
        """
        query = select(self.model).order_by(self.model.id).limit(limit + 1)  # type: ignore[attr-defined]
        if cursor is not None:
            query = query.where(self.model.id > cursor)  # type: ignore[attr-defined]
        result = await db.execute(query)
        rows = list(result.scalars().all())
        next_cursor = rows[-1].id if len(rows) > limit else None  # type: ignore[attr-defined]
        return rows[:limit], next_cursor

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs_in: list[CreateSchemaType],
    ) -> list[ModelType]:
        """Create multiple records in a single transaction.

        Uses db.add_all() + single commit + single refresh per object.
        """
        db_objs = [self.model(**obj_in.model_dump()) for obj_in in objs_in]
        db.add_all(db_objs)
        await db.commit()
        for obj in db_objs:
            await db.refresh(obj)
        return db_objs

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> ModelType | None:
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def count(self, db: AsyncSession) -> int:
        from sqlalchemy import func

        result = await db.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    async def get_cached_count(
        self,
        db: AsyncSession,
        *,
        redis_cache: Any | None = None,
        ttl: int = 60,
    ) -> int:
        """Return cached row count, falling back to DB and caching the result.

        Pass the application's RedisCache instance to enable caching.
        """
        cache_key = f"count:{self.model.__tablename__}"
        if redis_cache is not None:
            cached = await redis_cache.get(cache_key)
            if cached is not None:
                return int(cached)
        total = await self.count(db)
        if redis_cache is not None:
            await redis_cache.set(cache_key, total, ttl=ttl)
        return total
