"""Tests for the notification event-bus dispatcher."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.events.base import Event
from app.services.notifications import handle_notification_event


def _patch_dispatch(mocker, *, in_app=True, email=True, user="exists", notification=None):
    fake_db = mocker.AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield fake_db

    async def _fake_channel_enabled(_db, *, user_id, channel):
        if channel == "in_app":
            return in_app
        if channel == "email":
            return email
        return True

    mocker.patch("app.services.notifications._db_session", fake_session)
    mocker.patch(
        "app.services.notifications.channel_enabled",
        new=_fake_channel_enabled,
    )
    mock_user = None if user == "missing" else SimpleNamespace(id=7, email="user@example.com")
    mocker.patch("app.crud.user.user.get", new=mocker.AsyncMock(return_value=mock_user))
    if notification is None:
        notification = SimpleNamespace(id=11, title="Welcome", body="Hi")
    mocker.patch(
        "app.crud.notification.notification.create_for_user",
        new=mocker.AsyncMock(return_value=notification),
    )
    mocker.patch("app.services.notifications._push_websocket", new=mocker.AsyncMock())
    mock_email = mocker.MagicMock()
    mocker.patch("app.services.email.send_email_with_retry", mock_email)
    return fake_db, mock_email


class TestHandleNotificationEvent:
    @pytest.mark.asyncio
    async def test_disabled_returns_early(self, mocker):
        mock_settings = mocker.MagicMock(NOTIFICATION_ENABLED=False)
        mocker.patch("app.services.notifications.settings", mock_settings)
        mock_email = mocker.MagicMock()
        mocker.patch("app.services.email.send_email_with_retry", mock_email)

        await handle_notification_event(Event(event_type="user.created", payload={}, user_id=1))

        mock_email.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_without_user_id_is_noop(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker)

        await handle_notification_event(Event(event_type="user.created", payload={}))

        from app.crud.notification import notification as notification_crud

        notification_crud.create_for_user.assert_not_awaited()
        mock_email.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatches_to_in_app_and_email(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker)
        event = Event(
            event_type="user.created",
            payload={"title": "Welcome", "body": "Hi there"},
            user_id=7,
        )

        await handle_notification_event(event)

        from app.crud.notification import notification as notification_crud

        notification_crud.create_for_user.assert_awaited_once_with(
            fake_db, user_id=7, event_type="user.created", title="Welcome", body="Hi there"
        )
        mock_email.delay.assert_called_once_with(
            "user@example.com",
            "Welcome",
            "notification.html",
            {"title": "Welcome", "event_type": "user.created", "body": "Hi there"},
        )

    @pytest.mark.asyncio
    async def test_in_app_disabled_skips_row(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker, in_app=False)

        await handle_notification_event(
            Event(event_type="user.created", payload={"title": "Welcome"}, user_id=7)
        )

        from app.crud.notification import notification as notification_crud

        notification_crud.create_for_user.assert_not_awaited()
        mock_email.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_disabled_skips_task(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker, email=False)

        await handle_notification_event(
            Event(event_type="user.created", payload={"title": "Welcome"}, user_id=7)
        )

        from app.crud.notification import notification as notification_crud

        notification_crud.create_for_user.assert_awaited_once()
        mock_email.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_user_skips_email_but_keeps_in_app(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker, user="missing")

        await handle_notification_event(
            Event(event_type="user.created", payload={"title": "Welcome"}, user_id=7)
        )

        from app.crud.notification import notification as notification_crud

        notification_crud.create_for_user.assert_awaited_once()
        mock_email.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_email_enqueue_failure_does_not_raise(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker)
        mock_email.delay.side_effect = RuntimeError("broker down")

        await handle_notification_event(  # must not raise
            Event(event_type="user.created", payload={"title": "Welcome"}, user_id=7)
        )

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self, mocker):
        fake_db, mock_email = _patch_dispatch(mocker)

        @asynccontextmanager
        async def fake_session():
            raise RuntimeError("db down")
            yield mocker.AsyncMock()

        mocker.patch("app.services.notifications._db_session", fake_session)

        await handle_notification_event(  # must not raise
            Event(event_type="user.created", payload={}, user_id=7)
        )
