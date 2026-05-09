"""Unit tests for the task‑status SSE generator (no HTTP)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.endpoints.tasks import _stream_task_status
from app.models.task_status import TaskStatus


@pytest.mark.asyncio
async def test_task_status_generator_emits_complete():
    """Generator yields a 'complete' event when task is SUCCESS."""
    db = AsyncMock()
    task = MagicMock(spec=TaskStatus)
    task.task_id = "abc"
    task.status = "SUCCESS"

    # Create a chainable mock that returns the task from scalar_one_or_none
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = task
    db.execute.return_value = result_mock

    events = []
    async for event in _stream_task_status("abc", db):
        events.append(event)
        if "event: complete" in event:
            break

    assert any("event: complete" in e for e in events)
