"""CRUD operations for notification preferences and the in-app inbox."""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.schemas.notification import (
    NotificationCreate,
    NotificationPreferenceUpdate,
    NotificationUpdate,
)


class CRUDNotificationPreference(
    CRUDBase[NotificationPreference, NotificationPreferenceUpdate, NotificationPreferenceUpdate]
):
    async def get_for_user(
        self, db: AsyncSession, *, user_id: int
    ) -> NotificationPreference | None:
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, db: AsyncSession, *, user_id: int) -> NotificationPreference:
        """Return the user's preference row, creating default-enabled one if missing."""
        pref = await self.get_for_user(db, user_id=user_id)
        if pref is not None:
            return pref
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
        return pref

    async def update_for_user(
        self, db: AsyncSession, *, user_id: int, obj_in: NotificationPreferenceUpdate
    ) -> NotificationPreference:
        """Upsert preferences: create a default row when the user has none."""
        pref = await self.get_or_create(db, user_id=user_id)
        update_data = obj_in.model_dump(exclude_unset=True)
        if not update_data:
            return pref
        for field, value in update_data.items():
            setattr(pref, field, value)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
        return pref


class CRUDNotification(CRUDBase[Notification, NotificationCreate, NotificationUpdate]):
    async def create_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        event_type: str,
        title: str,
        body: str | None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            is_read=False,
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def get_for_user(
        self, db: AsyncSession, *, notification_id: int, user_id: int
    ) -> Notification | None:
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        unread_only: bool = False,
    ) -> list[Notification]:
        query = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .offset(skip)
            .limit(limit)
        )
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_for_user_cursor(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        cursor: int | None = None,
        size: int = 50,
        unread_only: bool = False,
    ) -> list[Notification]:
        """Keyset pagination: fetch the next page using ``WHERE id < cursor``."""
        query = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .limit(size + 1)
        )
        if cursor is not None:
            query = query.where(Notification.id < cursor)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        result = await db.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, db: AsyncSession, *, user_id: int) -> int:
        result = await db.execute(
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        return int(result.scalar_one())

    async def count_unread(self, db: AsyncSession, *, user_id: int) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return int(result.scalar_one())

    async def mark_read(self, db: AsyncSession, *, notification: Notification) -> Notification:
        if notification.is_read:
            return notification
        notification.is_read = True
        notification.read_at = datetime.now(UTC)
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification

    async def mark_all_read(self, db: AsyncSession, *, user_id: int) -> int:
        result = cast(
            CursorResult[Any],
            await db.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
                .values(is_read=True, read_at=datetime.now(UTC))
            ),
        )
        await db.commit()
        return int(result.rowcount or 0)


notification_preference = CRUDNotificationPreference(NotificationPreference)
notification = CRUDNotification(Notification)
