"""Tests for webhook backoff, delivery payload, and event dispatch."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.events.base import Event
from app.services.webhook import build_delivery_payload, compute_backoff, handle_event


class TestComputeBackoff:
    def test_exponential_growth(self):
        base = int(settings.WEBHOOK_BACKOFF_BASE_SECONDS)
        assert compute_backoff(1) == base
        assert compute_backoff(2) == base * 2
        assert compute_backoff(3) == base * 4

    def test_capped_at_max(self):
        assert compute_backoff(1000) == int(settings.WEBHOOK_BACKOFF_MAX_SECONDS)
        assert compute_backoff(30) == int(settings.WEBHOOK_BACKOFF_MAX_SECONDS)


class TestBuildDeliveryPayload:
    def test_payload_shape(self):
        event = Event(event_type="user.created", payload={"id": 1})
        payload = build_delivery_payload(event, delivery_id=7, attempt=2)
        assert payload["id"] == event.id
        assert payload["event_type"] == "user.created"
        assert payload["timestamp"] == event.timestamp
        assert payload["data"] == {"id": 1}
        assert payload["delivery_id"] == 7
        assert payload["attempt"] == 2


class TestHandleEvent:
    @pytest.mark.asyncio
    async def test_dispatches_to_matching_webhooks(self, mocker):
        event = Event(event_type="user.created", payload={"id": 1})
        mock_webhook = SimpleNamespace(id=10)
        mock_delivery = SimpleNamespace(id=5)

        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(return_value=[mock_webhook]),
        )
        mocker.patch(
            "app.crud.webhook.webhook.create_delivery",
            new=mocker.AsyncMock(return_value=mock_delivery),
        )
        mock_task = mocker.MagicMock()
        mocker.patch("app.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)

        from app.crud.webhook import webhook as webhook_crud

        webhook_crud.get_active_for_event_type.assert_awaited_once_with(
            fake_db, event_type="user.created"
        )
        webhook_crud.create_delivery.assert_awaited_once()
        mock_task.delay.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_no_webhooks_no_deliveries(self, mocker):
        event = Event(event_type="user.created", payload={})
        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(return_value=[]),
        )
        mocker.patch(
            "app.crud.webhook.webhook.create_delivery",
            new=mocker.AsyncMock(),
        )
        mock_task = mocker.MagicMock()
        mocker.patch("app.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)

        from app.crud.webhook import webhook as webhook_crud

        webhook_crud.create_delivery.assert_not_awaited()
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_returns_early(self, mocker):
        mock_settings = mocker.MagicMock(WEBHOOK_ENABLED=False)
        mocker.patch("app.services.webhook.settings", mock_settings)
        mock_task = mocker.MagicMock()
        mocker.patch("app.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(Event(event_type="user.created", payload={}))

        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_enqueue_failure_does_not_raise(self, mocker):
        event = Event(event_type="user.created", payload={})
        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(return_value=[SimpleNamespace(id=1)]),
        )
        mocker.patch(
            "app.crud.webhook.webhook.create_delivery",
            new=mocker.AsyncMock(return_value=SimpleNamespace(id=1)),
        )
        mock_task = mocker.MagicMock()
        mock_task.delay.side_effect = RuntimeError("broker down")
        mocker.patch("app.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)  # must not raise
