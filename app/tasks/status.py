"""Task status update operations."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_status import TaskStatus


async def update_task_status(
    db: AsyncSession,
    task_id: str,
    status: str,
    error: str | None = None,
):
    existing = await db.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
    task = existing.scalar_one_or_none()

    if task:
        task.status = status
        task.error = error
        if status in ("SUCCESS", "FAILURE"):
            task.completed_at = datetime.now(UTC)
    else:
        task = TaskStatus(
            task_id=task_id,
            status=status,
            error=error,
        )
        db.add(task)

    await db.commit()
