"""Tests for notification channel gating and the webhook channel preference."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.events.base import Event
from app.notifications.models.notification_preference import NotificationPreference
from app.notifications.services.notifications import (
    _channel_enabled_for_preference,
    channel_enabled,
)
from app.notifications.services.webhook import handle_event


class TestChannelEnabledForPreference:
    def test_all_channels_default_enabled(self):
        pref = NotificationPreference(
            user_id=1, email_enabled=True, in_app_enabled=True, webhook_enabled=True
        )
        assert _channel_enabled_for_preference(pref, "email") is True
        assert _channel_enabled_for_preference(pref, "in_app") is True
        assert _channel_enabled_for_preference(pref, "webhook") is True

    def test_opt_outs(self):
        pref = NotificationPreference(
            user_id=1, email_enabled=False, in_app_enabled=True, webhook_enabled=False
        )
        assert _channel_enabled_for_preference(pref, "email") is False
        assert _channel_enabled_for_preference(pref, "in_app") is True
        assert _channel_enabled_for_preference(pref, "webhook") is False


class TestChannelEnabled:
    @pytest.mark.asyncio
    async def test_defaults_enabled_without_row(self, mocker):
        db = mocker.AsyncMock()
        mocker.patch(
            "app.notifications.crud.notification.notification_preference.get_for_user",
            new=mocker.AsyncMock(return_value=None),
        )
        assert await channel_enabled(db, user_id=1, channel="email") is True
        assert await channel_enabled(db, user_id=1, channel="webhook") is True

    @pytest.mark.asyncio
    async def test_respects_row(self, mocker):
        db = mocker.AsyncMock()
        mocker.patch(
            "app.notifications.crud.notification.notification_preference.get_for_user",
            new=mocker.AsyncMock(
                return_value=NotificationPreference(
                    user_id=1, email_enabled=False, in_app_enabled=True, webhook_enabled=True
                )
            ),
        )
        assert await channel_enabled(db, user_id=1, channel="email") is False
        assert await channel_enabled(db, user_id=1, channel="in_app") is True


class TestWebhookChannelGate:
    @pytest.mark.asyncio
    async def test_skips_dispatch_when_webhook_channel_disabled(self, mocker):
        event = Event(event_type="user.created", payload={}, user_id=3)
        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.notifications.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.notifications.services.notifications.channel_enabled",
            new=mocker.AsyncMock(return_value=False),
        )
        mocker.patch(
            "app.notifications.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(),
        )
        mocker.patch(
            "app.notifications.crud.webhook.webhook.create_delivery", new=mocker.AsyncMock()
        )
        mock_task = mocker.MagicMock()
        mocker.patch("app.notifications.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)

        from app.notifications.crud.webhook import webhook as webhook_crud

        webhook_crud.get_active_for_event_type.assert_not_awaited()
        webhook_crud.create_delivery.assert_not_awaited()
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatches_when_webhook_channel_enabled(self, mocker):
        event = Event(event_type="user.created", payload={}, user_id=3)
        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.notifications.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.notifications.services.notifications.channel_enabled",
            new=mocker.AsyncMock(return_value=True),
        )
        mocker.patch(
            "app.notifications.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(return_value=[SimpleNamespace(id=10)]),
        )
        mocker.patch(
            "app.notifications.crud.webhook.webhook.create_delivery",
            new=mocker.AsyncMock(return_value=SimpleNamespace(id=5)),
        )
        mock_task = mocker.MagicMock()
        mocker.patch("app.notifications.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)

        mock_task.delay.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_event_without_user_id_is_not_gated(self, mocker):
        event = Event(event_type="user.created", payload={})
        fake_db = mocker.AsyncMock()

        @asynccontextmanager
        async def fake_session():
            yield fake_db

        mocker.patch("app.notifications.services.webhook._db_session", fake_session)
        mocker.patch(
            "app.notifications.crud.webhook.webhook.get_active_for_event_type",
            new=mocker.AsyncMock(return_value=[SimpleNamespace(id=10)]),
        )
        mocker.patch(
            "app.notifications.crud.webhook.webhook.create_delivery",
            new=mocker.AsyncMock(return_value=SimpleNamespace(id=5)),
        )
        mock_task = mocker.MagicMock()
        mocker.patch("app.notifications.tasks.webhook.deliver_webhook", mock_task)

        await handle_event(event)

        mock_task.delay.assert_called_once_with(5)
