"""Task trigger and status endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.task_status import TaskStatus
from app.tasks.email import send_email_notification

router = APIRouter()


class EmailTaskRequest(BaseModel):
    recipient: str
    subject: str
    body: str


@router.post("/email/send")
async def trigger_email_task(task_data: EmailTaskRequest):
    task = send_email_notification.delay(
        task_data.recipient,
        task_data.subject,
        task_data.body,
    )
    return {"task_id": task.id, "status": "PENDING"}


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
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
