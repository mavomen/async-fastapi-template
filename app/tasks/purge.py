"""Celery task to purge soft-deleted records past their retention window."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import sessionmanager

logger = logging.getLogger("app.tasks.purge")


@celery_app.task(name="app.tasks.purge.purge_soft_deleted")  # type: ignore[untyped-decorator]
def purge_soft_deleted() -> dict[str, int]:
    """Hard-delete records that have been soft-deleted beyond the retention window.

    Returns a dict mapping table name to the number of rows purged.
    """
    return asyncio.get_event_loop().run_until_complete(_purge_soft_deleted_async())


async def _purge_soft_deleted_async() -> dict[str, int]:
    from app.identity.models.api_key import ApiKey
    from app.identity.models.user import User
    from app.notifications.models.notification import Notification
    from app.notifications.models.webhook import Webhook

    models = [User, Notification, Webhook, ApiKey]
    results: dict[str, int] = {}
    cutoff = datetime.now(UTC) - timedelta(days=settings.SOFT_DELETE_PURGE_DAYS)

    async with sessionmanager.writer_session() as db:
        for model in models:
            stmt = delete(model).where(
                model.deleted_at.isnot(None),  # type: ignore[attr-defined]
                model.deleted_at < cutoff,  # type: ignore[attr-defined]
            )
            result = await db.execute(stmt)
            count: int = result.rowcount  # type: ignore[attr-defined]
            if count > 0:
                logger.info("Purged %d soft-deleted %s records", count, model.__tablename__)
            results[model.__tablename__] = count

        await db.commit()

    return results
