"""Test get_task_status endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_status import TaskStatus


@pytest.mark.asyncio
async def test_get_task_status(async_client: AsyncClient, db_session: AsyncSession):
    task = TaskStatus(task_id="get-status", name="email", status="SUCCESS")
    db_session.add(task)
    await db_session.commit()

    resp = await async_client.get("/api/v1/tasks/get-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == "get-status"
    assert data["status"] == "SUCCESS"
