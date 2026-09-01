"""Celery task: dunning sweep.

Advances every due payment-failure schedule by one tick: reminders while
retry positions remain, suspension once they are exhausted. Gated behind
``BILLING_DUNNING_ENABLED`` so enabling dunning is an explicit operator
decision.
"""

import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import sessionmanager

logger = logging.getLogger("app.tasks.dunning")


@celery_app.task(name="app.tasks.dunning.process_dunning")  # type: ignore[untyped-decorator]
def process_dunning() -> dict[str, int]:
    """Advance due dunning schedules (reminders + suspensions)."""
    if not settings.BILLING_DUNNING_ENABLED:
        return {"due": 0, "reminded": 0, "suspended": 0, "failed": 0, "disabled": 1}
    result = asyncio.get_event_loop().run_until_complete(_process_dunning_async())
    result["disabled"] = 0
    return result


async def _process_dunning_async() -> dict[str, int]:
    from app.billing.services import dunning as dunning_service
    from app.events import get_event_bus as _get_bus

    bus = await _get_bus()
    async with sessionmanager.writer_session() as db:
        try:
            stats = await dunning_service.process_due_retries(db, bus)
            await db.commit()
            return stats
        except Exception:
            await db.rollback()
            raise


__all__ = ["process_dunning"]
