"""Tests for notification preference and inbox REST endpoints."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.main import app


def make_pref(**overrides):
    now = datetime.now(UTC)
    base = SimpleNamespace(
        id=1,
        user_id=1,
        email_enabled=True,
        in_app_enabled=True,
        webhook_enabled=True,
        created_at=now,
        updated_at=now,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def make_notification(**overrides):
    now = datetime.now(UTC)
    base = SimpleNamespace(
        id=10,
        event_type="user.created",
        title="Welcome",
        body="Hi",
        is_read=False,
        read_at=None,
        created_at=now,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def make_user():
    user = MagicMock()
    user.id = 1
    user.is_active = True
    user.is_superuser = True
    user.roles = []
    return user


def override_user(user):
    from app.api.deps import get_current_user, get_current_user_or_api_key

    async def _fake():
        return user

    app.dependency_overrides[get_current_user] = _fake
    app.dependency_overrides[get_current_user_or_api_key] = _fake


def override_event_bus(bus):
    from app.api.deps import get_event_bus

    async def _fake():
        return bus

    app.dependency_overrides[get_event_bus] = _fake


def clear_overrides():
    from app.api.deps import get_current_user, get_current_user_or_api_key, get_db, get_event_bus

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_or_api_key, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_event_bus, None)


class TestAuth:
    def test_get_preferences_requires_auth(self, client):
        assert client.get("/api/v1/notifications/preferences").status_code == 401

    def test_update_preferences_requires_auth(self, client):
        resp = client.put("/api/v1/notifications/preferences", json={"email_enabled": False})
        assert resp.status_code == 401

    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/notifications").status_code == 401

    def test_mark_read_requires_auth(self, client):
        assert client.post("/api/v1/notifications/1/read").status_code == 401

    def test_mark_all_read_requires_auth(self, client):
        assert client.post("/api/v1/notifications/read-all").status_code == 401

    def test_delete_requires_auth(self, client):
        assert client.delete("/api/v1/notifications/1").status_code == 401

    def test_test_notification_requires_auth(self, client):
        assert client.post("/api/v1/notifications/test").status_code == 401


class TestPreferenceEndpoints:
    def test_get_preferences_creates_defaults(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification_preference.get_or_create",
            new=AsyncMock(return_value=make_pref()),
        )
        try:
            resp = client.get("/api/v1/notifications/preferences")
            assert resp.status_code == 200
            data = resp.json()
            assert data["user_id"] == 1
            assert data["email_enabled"] is True
        finally:
            clear_overrides()

    def test_update_preferences(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification_preference.update_for_user",
            new=AsyncMock(return_value=make_pref(email_enabled=False)),
        )
        try:
            resp = client.put("/api/v1/notifications/preferences", json={"email_enabled": False})
            assert resp.status_code == 200
            assert resp.json()["email_enabled"] is False
        finally:
            clear_overrides()


class TestInboxEndpoints:
    def test_list_notifications(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.list_for_user",
            new=AsyncMock(return_value=[make_notification()]),
        )
        mocker.patch(
            "app.crud.notification.notification.count_for_user",
            new=AsyncMock(return_value=1),
        )
        mocker.patch(
            "app.crud.notification.notification.count_unread",
            new=AsyncMock(return_value=1),
        )
        try:
            resp = client.get("/api/v1/notifications")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["unread_count"] == 1
            assert data["items"][0]["title"] == "Welcome"
        finally:
            clear_overrides()

    def test_mark_read(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.get_for_user",
            new=AsyncMock(return_value=make_notification()),
        )
        mocker.patch(
            "app.crud.notification.notification.mark_read",
            new=AsyncMock(return_value=make_notification(is_read=True)),
        )
        try:
            resp = client.post("/api/v1/notifications/10/read")
            assert resp.status_code == 200
            assert resp.json()["is_read"] is True
        finally:
            clear_overrides()

    def test_mark_read_other_users_notification_is_404(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.get_for_user",
            new=AsyncMock(return_value=None),
        )
        try:
            assert client.post("/api/v1/notifications/10/read").status_code == 404
        finally:
            clear_overrides()

    def test_mark_all_read(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.mark_all_read",
            new=AsyncMock(return_value=3),
        )
        try:
            resp = client.post("/api/v1/notifications/read-all")
            assert resp.status_code == 200
            assert resp.json() == {"updated": 3}
        finally:
            clear_overrides()

    def test_delete_notification(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.get_for_user",
            new=AsyncMock(return_value=make_notification()),
        )
        mocker.patch(
            "app.crud.notification.notification.delete",
            new=AsyncMock(return_value=make_notification()),
        )
        try:
            assert client.delete("/api/v1/notifications/10").status_code == 204
        finally:
            clear_overrides()

    def test_delete_other_users_notification_is_404(self, client, mocker):
        override_user(make_user())
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.notification.notification.get_for_user",
            new=AsyncMock(return_value=None),
        )
        try:
            assert client.delete("/api/v1/notifications/10").status_code == 404
        finally:
            clear_overrides()


class TestTestNotification:
    def test_publishes_event_for_current_user(self, client):
        override_user(make_user())
        bus = MagicMock()
        bus.publish = AsyncMock()
        override_event_bus(bus)
        try:
            resp = client.post(
                "/api/v1/notifications/test",
                json={"title": "Hello", "body": "World"},
            )
            assert resp.status_code == 202
            data = resp.json()
            assert data["event_type"] == "notification.test"
            bus.publish.assert_awaited_once()
            event = bus.publish.await_args.args[0]
            assert event.user_id == 1
            assert event.payload == {"title": "Hello", "body": "World"}
        finally:
            clear_overrides()

    def test_publishes_with_default_payload(self, client):
        override_user(make_user())
        bus = MagicMock()
        bus.publish = AsyncMock()
        override_event_bus(bus)
        try:
            resp = client.post("/api/v1/notifications/test")
            assert resp.status_code == 202
            event = bus.publish.await_args.args[0]
            assert event.payload["title"] == "Test notification"
        finally:
            clear_overrides()
