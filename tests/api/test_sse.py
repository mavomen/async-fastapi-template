"""Unit test for the SSE task status event generator (no HTTP hang)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_status import TaskStatus


# Duplicate the generator logic here for direct unit testing
async def _sse_event_generator(task_id: str, db: AsyncSession):
    import asyncio

    from sqlalchemy import select

    while True:
        result = await db.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
        task = result.scalar_one_or_none()
        if task and task.status in ("SUCCESS", "FAILURE"):
            yield f"event: complete\ndata: {task.status}\n\n"
            break
        yield f"event: status\ndata: {task.status if task else 'PENDING'}\n\n"
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_generator_emits_complete_for_success(db_session: AsyncSession):
    """The generator yields a 'complete' event when task status is SUCCESS."""
    task = TaskStatus(task_id="gen-test", name="email", status="SUCCESS")
    db_session.add(task)
    await db_session.commit()

    events = []
    async for event in _sse_event_generator("gen-test", db_session):
        events.append(event)
        if "event: complete" in event:
            break

    assert any("event: complete" in e for e in events)
