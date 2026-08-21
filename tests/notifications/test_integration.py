"""Integration tests for the notification dispatcher (real Postgres)."""

import pytest
from sqlalchemy import select

from app.events.base import Event
from app.identity.models.user import User
from app.notifications.models.notification import Notification
from app.notifications.models.notification_preference import NotificationPreference
from app.notifications.services.notifications import handle_notification_event


@pytest.mark.asyncio
async def _make_user(db_session, email="dispatch@example.com", username="dispatch-user") -> User:
    user = User(email=email, username=username, hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_dispatch_creates_in_app_row_and_enqueues_email(db_session, mocker):
    user = await _make_user(db_session)
    mock_email = mocker.MagicMock()
    mocker.patch("app.notifications.services.email.send_email_with_retry", mock_email)
    mocker.patch("app.notifications.services.notifications._push_websocket", new=mocker.AsyncMock())

    await handle_notification_event(
        Event(
            event_type="user.created",
            payload={"title": "Welcome", "body": "Hi"},
            user_id=user.id,
        )
    )

    rows = (
        (await db_session.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].title == "Welcome"
    assert rows[0].body == "Hi"
    mock_email.delay.assert_called_once_with(
        "dispatch@example.com",
        "Welcome",
        "notification.html",
        {"title": "Welcome", "event_type": "user.created", "body": "Hi"},
    )


@pytest.mark.asyncio
async def test_dispatch_without_user_id_creates_nothing(db_session, mocker):
    mock_email = mocker.MagicMock()
    mocker.patch("app.notifications.services.email.send_email_with_retry", mock_email)

    await handle_notification_event(Event(event_type="user.created", payload={}))

    rows = (await db_session.execute(select(Notification))).scalars().all()
    assert rows == []
    mock_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_in_app_disabled_skips_row(db_session, mocker):
    user = await _make_user(db_session)
    db_session.add(NotificationPreference(user_id=user.id, in_app_enabled=False))
    await db_session.commit()
    mock_email = mocker.MagicMock()
    mocker.patch("app.notifications.services.email.send_email_with_retry", mock_email)
    mocker.patch("app.notifications.services.notifications._push_websocket", new=mocker.AsyncMock())

    await handle_notification_event(
        Event(event_type="user.created", payload={"title": "Welcome"}, user_id=user.id)
    )

    rows = (
        (await db_session.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert rows == []
    mock_email.delay.assert_called_once()


@pytest.mark.asyncio
async def test_email_disabled_skips_task(db_session, mocker):
    user = await _make_user(db_session)
    db_session.add(NotificationPreference(user_id=user.id, email_enabled=False))
    await db_session.commit()
    mock_email = mocker.MagicMock()
    mocker.patch("app.notifications.services.email.send_email_with_retry", mock_email)
    mocker.patch("app.notifications.services.notifications._push_websocket", new=mocker.AsyncMock())

    await handle_notification_event(
        Event(event_type="user.created", payload={"title": "Welcome"}, user_id=user.id)
    )

    rows = (
        (await db_session.execute(select(Notification).where(Notification.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    mock_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_failure_does_not_raise(db_session, mocker):
    user = await _make_user(db_session)
    mocker.patch(
        "app.notifications.services.notifications.channel_enabled",
        side_effect=RuntimeError("db exploded"),
    )

    await handle_notification_event(  # must not raise
        Event(event_type="user.created", payload={"title": "Welcome"}, user_id=user.id)
    )
