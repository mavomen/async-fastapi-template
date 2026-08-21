"""Base CRUD class with common async database operations."""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base, SoftDeleteMixin

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

_SOFT_DELETE_TABLES: set[str] = set()


def _has_soft_delete(model: type[Base]) -> bool:
    """Check whether a model class uses SoftDeleteMixin."""
    return any(issubclass(cls, SoftDeleteMixin) for cls in model.__mro__)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base class for CRUD operations."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get(
        self, db: AsyncSession, id: int, *, include_deleted: bool = False
    ) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        if not include_deleted and _has_soft_delete(self.model):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> list[ModelType]:
        stmt = select(self.model).order_by(self.model.id).offset(skip).limit(limit)  # type: ignore[attr-defined]
        if not include_deleted and _has_soft_delete(self.model):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_multi_cursor(
        self,
        db: AsyncSession,
        *,
        cursor: int | None = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int | None]:
        """Keyset (cursor) pagination — WHERE id > cursor ORDER BY id LIMIT limit+1.

        Returns (items, next_cursor) where next_cursor is the last id to
        pass back as the cursor on the next request.
        """
        stmt = select(self.model).order_by(self.model.id).limit(limit + 1)  # type: ignore[attr-defined]
        if cursor is not None:
            stmt = stmt.where(self.model.id > cursor)  # type: ignore[attr-defined]
        if not include_deleted and _has_soft_delete(self.model):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor = rows[-1].id if len(rows) > limit else None  # type: ignore[attr-defined]
        return rows[:limit], next_cursor

    async def count(self, db: AsyncSession, *, include_deleted: bool = False) -> int:
        stmt = select(func.count()).select_from(self.model)
        if not include_deleted and _has_soft_delete(self.model):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await db.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

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
        """Soft-delete (set deleted_at) when the model uses SoftDeleteMixin, else hard-delete."""
        obj = await self.get(db, id)
        if obj is None:
            return None
        if _has_soft_delete(self.model):
            obj.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
            db.add(obj)
            await db.commit()
            await db.refresh(obj)
        else:
            await db.delete(obj)
            await db.commit()
        return obj

    async def restore(self, db: AsyncSession, *, id: int) -> ModelType | None:
        """Restore a soft-deleted record by clearing deleted_at."""
        if not _has_soft_delete(self.model):
            return None
        obj = await self.get(db, id, include_deleted=True)
        if obj is None:
            return None
        deleted_at: datetime | None = getattr(obj, "deleted_at", None)
        if deleted_at is None:
            return None
        obj.deleted_at = None  # type: ignore[attr-defined]
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def purge(self, db: AsyncSession, *, older_than_days: int = 90) -> int:
        """Hard-delete records that have been soft-deleted for longer than N days."""
        if not _has_soft_delete(self.model):
            return 0
        from datetime import timedelta

        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = cutoff - timedelta(days=older_than_days)
        from sqlalchemy import delete

        stmt = delete(self.model).where(
            self.model.deleted_at.isnot(None),  # type: ignore[attr-defined]
            self.model.deleted_at < cutoff,  # type: ignore[attr-defined]
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount  # type: ignore[attr-defined,no-any-return]

    # ------------------------------------------------------------------
    # Cached count
    # ------------------------------------------------------------------

    async def get_cached_count(
        self,
        db: AsyncSession,
        *,
        redis_cache: Any | None = None,
        ttl: int = 60,
        include_deleted: bool = False,
    ) -> int:
        """Return cached row count, falling back to DB and caching the result.

        Pass the application's RedisCache instance to enable caching.
        """
        suffix = ":deleted" if include_deleted else ""
        cache_key = f"count:{self.model.__tablename__}{suffix}"
        if redis_cache is not None:
            cached = await redis_cache.get(cache_key)
            if cached is not None:
                return int(cached)
        total = await self.count(db, include_deleted=include_deleted)
        if redis_cache is not None:
            await redis_cache.set(cache_key, total, ttl=ttl)
        return total
