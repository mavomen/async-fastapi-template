"""Unit tests for update_task_status."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.tasks.status import update_task_status
from app.models.task_status import TaskStatus


@pytest.mark.asyncio
async def test_update_status_success():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    await update_task_status(db, "task-123", "SUCCESS", error=None)
    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_existing():
    db = AsyncMock()
    existing = TaskStatus(task_id="task-456", status="PENDING")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    db.execute.return_value = result_mock

    await update_task_status(db, "task-456", "FAILURE", error="timeout")
    assert existing.status == "FAILURE"
    assert existing.error == "timeout"
    db.commit.assert_called_once()
