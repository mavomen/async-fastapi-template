"""Cover the task status endpoint with a real DB row."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_status import TaskStatus


@pytest.mark.asyncio
async def test_task_status_found(async_client: AsyncClient, db_session: AsyncSession):
    task = TaskStatus(task_id="cov-test", name="email", status="SUCCESS")
    db_session.add(task)
    await db_session.commit()
    resp = await async_client.get("/api/v1/tasks/cov-test")
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUCCESS"
