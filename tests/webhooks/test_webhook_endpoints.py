"""Tests for the webhook REST endpoints."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.main import app


def make_webhook(**overrides):
    now = datetime.now(UTC)
    base = SimpleNamespace(
        id=1,
        name="my webhook",
        url="https://example.com/hook",
        event_types=None,
        is_active=True,
        last_delivery_at=None,
        last_status=None,
        failure_count=0,
        created_at=now,
        updated_at=now,
        tenant_id=None,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def make_delivery(**overrides):
    now = datetime.now(UTC)
    base = SimpleNamespace(
        id=10,
        webhook_id=1,
        event_id="evt-001",
        event_type="user.created",
        attempt=1,
        max_attempts=6,
        status="delivered",
        response_status=200,
        response_body="ok",
        error=None,
        next_retry_at=None,
        delivered_at=now,
        created_at=now,
        updated_at=now,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def make_user(superuser=False, tenant_id=None):
    user = MagicMock()
    user.id = 1
    user.tenant_id = tenant_id
    user.is_active = True
    user.is_superuser = superuser
    user.roles = []
    return user


def override_user(mocker, user):
    from app.api.deps import get_current_user, get_current_user_or_api_key

    async def _fake():
        return user

    app.dependency_overrides[get_current_user] = _fake
    app.dependency_overrides[get_current_user_or_api_key] = _fake


def clear_overrides():
    from app.api.deps import get_current_user, get_current_user_or_api_key, get_db

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_or_api_key, None)
    app.dependency_overrides.pop(get_db, None)


class TestAuth:
    def test_create_requires_auth(self, client):
        resp = client.post("/api/v1/webhooks", json={"name": "x", "url": "https://example.com/h"})
        assert resp.status_code == 401

    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/webhooks").status_code == 401

    def test_get_requires_auth(self, client):
        assert client.get("/api/v1/webhooks/1").status_code == 401

    def test_patch_requires_auth(self, client):
        resp = client.patch("/api/v1/webhooks/1", json={"name": "x"})
        assert resp.status_code == 401

    def test_delete_requires_auth(self, client):
        assert client.delete("/api/v1/webhooks/1").status_code == 401

    def test_ping_requires_auth(self, client):
        assert client.post("/api/v1/webhooks/1/ping").status_code == 401

    def test_deliveries_requires_auth(self, client):
        assert client.get("/api/v1/webhooks/1/deliveries").status_code == 401


class TestPermissions:
    def test_create_requires_permission(self, client, mocker):
        override_user(mocker, make_user())
        try:
            resp = client.post(
                "/api/v1/webhooks", json={"name": "x", "url": "https://example.com/h"}
            )
            assert resp.status_code == 403
        finally:
            clear_overrides()

    def test_patch_requires_permission(self, client, mocker):
        override_user(mocker, make_user())
        try:
            assert client.patch("/api/v1/webhooks/1", json={"name": "x"}).status_code == 403
        finally:
            clear_overrides()

    def test_delete_requires_permission(self, client, mocker):
        override_user(mocker, make_user())
        try:
            assert client.delete("/api/v1/webhooks/1").status_code == 403
        finally:
            clear_overrides()

    def test_ping_requires_permission(self, client, mocker):
        override_user(mocker, make_user())
        try:
            assert client.post("/api/v1/webhooks/1/ping").status_code == 403
        finally:
            clear_overrides()


class TestCrudEndpoints:
    def test_create_returns_secret_once(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.webhook.webhook.create_with_secret",
            new=AsyncMock(return_value=(make_webhook(), "super-secret")),
        )
        try:
            resp = client.post(
                "/api/v1/webhooks", json={"name": "x", "url": "https://example.com/h"}
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["secret"] == "super-secret"
            assert data["name"] == "my webhook"
        finally:
            clear_overrides()

    def test_list_webhooks(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.webhook.webhook.list_for_tenant",
            new=AsyncMock(return_value=[make_webhook()]),
        )
        try:
            resp = client.get("/api/v1/webhooks")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert "secret" not in data[0]
        finally:
            clear_overrides()

    def test_get_webhook(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=make_webhook()))
        try:
            resp = client.get("/api/v1/webhooks/1")
            assert resp.status_code == 200
            assert resp.json()["name"] == "my webhook"
        finally:
            clear_overrides()

    def test_get_webhook_not_found(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=None))
        try:
            assert client.get("/api/v1/webhooks/1").status_code == 404
        finally:
            clear_overrides()

    def test_get_other_tenant_webhook_is_404(self, client, mocker):
        user = make_user(superuser=False, tenant_id=2)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch(
            "app.crud.webhook.webhook.get",
            new=AsyncMock(return_value=make_webhook(tenant_id=99)),
        )
        try:
            assert client.get("/api/v1/webhooks/1").status_code == 404
        finally:
            clear_overrides()

    def test_patch_webhook(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=make_webhook()))
        mocker.patch(
            "app.crud.webhook.webhook.update",
            new=AsyncMock(return_value=make_webhook(name="renamed")),
        )
        try:
            resp = client.patch("/api/v1/webhooks/1", json={"name": "renamed"})
            assert resp.status_code == 200
            assert resp.json()["name"] == "renamed"
        finally:
            clear_overrides()

    def test_delete_webhook(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=make_webhook()))
        mocker.patch("app.crud.webhook.webhook.delete", new=AsyncMock(return_value=make_webhook()))
        try:
            assert client.delete("/api/v1/webhooks/1").status_code == 204
        finally:
            clear_overrides()

    def test_ping_creates_delivery(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=make_webhook()))
        mocker.patch(
            "app.crud.webhook.webhook.create_delivery",
            new=AsyncMock(return_value=make_delivery()),
        )
        mock_task = MagicMock()
        mocker.patch("app.tasks.webhook.deliver_webhook", mock_task)
        try:
            resp = client.post("/api/v1/webhooks/1/ping")
            assert resp.status_code == 202
            assert resp.json()["event_type"] == "user.created"
            mock_task.delay.assert_called_once()
        finally:
            clear_overrides()

    def test_list_deliveries(self, client, mocker):
        user = make_user(superuser=True)
        override_user(mocker, user)
        mocker.patch("app.api.deps.get_db", lambda: AsyncMock())
        mocker.patch("app.crud.webhook.webhook.get", new=AsyncMock(return_value=make_webhook()))
        mocker.patch(
            "app.crud.webhook.webhook.list_deliveries",
            new=AsyncMock(return_value=[make_delivery()]),
        )
        try:
            resp = client.get("/api/v1/webhooks/1/deliveries")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["status"] == "delivered"
        finally:
            clear_overrides()
