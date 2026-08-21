"""Tests for email task trigger endpoint."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_trigger_email_task(async_client: AsyncClient):
    with patch("app.notifications.tasks.email.send_email_notification.delay") as mock_delay:
        mock_delay.return_value.id = "fake-id"
        resp = await async_client.post(
            "/api/v1/tasks/email/send",
            json={"recipient": "test@test.com", "subject": "Hi", "body": "Hello"},
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] == "fake-id"
