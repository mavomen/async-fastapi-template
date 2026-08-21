"""Task trigger and status endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.deps import get_read_db
from app.models.task_status import TaskStatus
from app.notifications.tasks.email import send_email_notification

router = APIRouter()


class EmailTaskRequest(BaseModel):
    recipient: str
    subject: str
    body: str


async def _stream_task_status(task_id: str, db: AsyncSession) -> Any:
    """Emit SSE events for a task's status (extracted for testing)."""
    import asyncio

    while True:
        result = await db.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
        task = result.scalar_one_or_none()
        if task and task.status in ("SUCCESS", "FAILURE"):
            yield f"event: complete\ndata: {task.status}\n\n"
            break
        yield f"event: status\ndata: {task.status if task else 'PENDING'}\n\n"
        await asyncio.sleep(2)


@router.post(
    "/email/send",
    summary="Send an email notification",
    description="Trigger a background task to send an email notification. "
    "Returns the task ID for status tracking.",
    responses={
        200: {"description": "Task triggered"},
    },
)
async def trigger_email_task(task_data: EmailTaskRequest) -> dict[str, Any]:
    task = send_email_notification.delay(
        task_data.recipient,
        task_data.subject,
        task_data.body,
    )
    return {"task_id": task.id, "status": "PENDING"}


@router.get(
    "/{task_id}",
    summary="Get task status",
    description="Check the status of a previously triggered background task.",
    responses={
        200: {"description": "Task status details"},
        404: {"description": "Task not found"},
    },
)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_read_db),
) -> dict[str, Any] | None:
    result = await db.execute(select(TaskStatus).where(TaskStatus.task_id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "error": task.error,
        "completed_at": task.completed_at,
    }


@router.get("/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_read_db),
) -> Any:
    """Stream task status updates via Server-Sent Events."""
    return StreamingResponse(
        _stream_task_status(task_id, db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
