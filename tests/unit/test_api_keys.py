"""Tests for API key generation, CRUD, auth flow, and endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import generate_api_key, verify_api_key


class TestKeyGeneration:
    def test_generates_correct_format(self):
        raw, hashed, prefix = generate_api_key()
        assert raw.startswith("ak_")
        assert len(raw) > 20
        assert len(hashed) == 64
        assert prefix == raw[:10]
        assert len(prefix) == 10

    def test_hash_is_deterministic(self):
        raw, hashed, _ = generate_api_key()
        assert verify_api_key(raw, hashed) is True

    def test_wrong_key_fails(self):
        _, hashed, _ = generate_api_key()
        assert verify_api_key("ak_wrongkey1234567890", hashed) is False

    def test_generates_unique_keys(self):
        keys = {generate_api_key()[0] for _ in range(100)}
        assert len(keys) == 100


class TestCRUDApiKeyVerify:
    @pytest.mark.asyncio
    async def test_verify_valid_key(self, mocker):
        mock_key = MagicMock()
        mock_key.id = 1
        mock_key.user_id = 1
        mock_key.is_active = True
        mock_key.hashed_key = "abc123"
        mock_key.expires_at = None
        mock_key.scopes = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mocker.patch("app.crud.api_key.verify_api_key", return_value=True)

        from app.crud.api_key import api_key as crud_api_key

        result = await crud_api_key.verify(mock_db, raw_key="ak_testkey1234")
        assert result is not None
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_verify_inactive_key_returns_none(self, mocker):
        mock_key = MagicMock()
        mock_key.is_active = False
        mock_key.hashed_key = "abc123"
        mock_key.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mocker.patch("app.crud.api_key.verify_api_key", return_value=True)

        from app.crud.api_key import api_key as crud_api_key

        result = await crud_api_key.verify(mock_db, raw_key="ak_testkey1234")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_wrong_prefix_returns_none(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        from app.crud.api_key import api_key as crud_api_key

        result = await crud_api_key.verify(mock_db, raw_key="ak_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_wrong_hash_returns_none(self, mocker):
        mock_key = MagicMock()
        mock_key.is_active = True
        mock_key.hashed_key = "abc123"
        mock_key.expires_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mocker.patch("app.crud.api_key.verify_api_key", return_value=False)

        from app.crud.api_key import api_key as crud_api_key

        result = await crud_api_key.verify(mock_db, raw_key="ak_testkey1234")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_expired_key_returns_none(self, mocker):
        from datetime import UTC, datetime, timedelta

        mock_key = MagicMock()
        mock_key.is_active = True
        mock_key.hashed_key = "abc123"
        mock_key.expires_at = datetime.now(UTC) - timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_key

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mocker.patch("app.crud.api_key.verify_api_key", return_value=True)

        from app.crud.api_key import api_key as crud_api_key

        result = await crud_api_key.verify(mock_db, raw_key="ak_testkey1234")
        assert result is None


class TestApiKeyEndpoints:
    def test_create_api_key_no_auth(self, client):
        resp = client.post("/api/v1/auth/api-keys", json={"name": "test-key"})
        assert resp.status_code == 401

    def test_list_api_keys_no_auth(self, client):
        resp = client.get("/api/v1/auth/api-keys")
        assert resp.status_code == 401

    def test_delete_api_key_no_auth(self, client):
        resp = client.delete("/api/v1/auth/api-keys/1")
        assert resp.status_code == 401

    def test_create_api_key_requires_permission(self, client, mocker):
        async def _fake_get_current_user():
            user = mocker.MagicMock()
            user.id = 1
            user.tenant_id = 2
            user.is_active = True
            user.is_superuser = False
            user.roles = []
            return user

        from app.api.deps import get_current_user_or_api_key
        from app.main import app

        app.dependency_overrides[get_current_user_or_api_key] = _fake_get_current_user
        try:
            resp = client.post("/api/v1/auth/api-keys", json={"name": "test-key"})
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_current_user_or_api_key, None)

    def test_create_api_key_as_superuser(self, client, mocker):
        from datetime import UTC, datetime

        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.is_superuser = True

        async def _fake_user():
            return mock_user

        now = datetime.now(UTC)
        mock_key_obj = mocker.MagicMock()
        mock_key_obj.id = 1
        mock_key_obj.name = "my-key"
        mock_key_obj.key_prefix = "ak_abc123"
        mock_key_obj.scopes = None
        mock_key_obj.is_active = True
        mock_key_obj.last_used_at = None
        mock_key_obj.expires_at = None
        mock_key_obj.created_at = now
        mock_key_obj.updated_at = now

        from app.api.deps import get_current_user_or_api_key, get_db
        from app.main import app

        app.dependency_overrides[get_current_user_or_api_key] = _fake_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        mocker.patch(
            "app.crud.api_key.generate_api_key",
            return_value=("ak_rawkey1234567890", "hash", "ak_abc123"),
        )
        mocker.patch(
            "app.crud.api_key.CRUDApiKey.create_with_raw_key",
            return_value=(mock_key_obj, "ak_rawkey1234567890"),
        )

        try:
            resp = client.post("/api/v1/auth/api-keys", json={"name": "my-key"})
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "my-key"
            assert data["raw_key"] == "ak_rawkey1234567890"
        finally:
            app.dependency_overrides.pop(get_current_user_or_api_key, None)
            app.dependency_overrides.pop(get_db, None)

    def test_list_api_keys(self, client, mocker):
        from datetime import UTC, datetime

        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.is_superuser = True

        async def _fake_user():
            return mock_user

        now = datetime.now(UTC)
        mock_key_obj = mocker.MagicMock()
        mock_key_obj.id = 1
        mock_key_obj.name = "my-key"
        mock_key_obj.key_prefix = "ak_abc123"
        mock_key_obj.scopes = None
        mock_key_obj.is_active = True
        mock_key_obj.last_used_at = None
        mock_key_obj.expires_at = None
        mock_key_obj.created_at = now
        mock_key_obj.updated_at = now

        from app.api.deps import get_current_user, get_db
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        mocker.patch("app.crud.api_key.CRUDApiKey.get_active_for_user", return_value=[mock_key_obj])

        try:
            resp = client.get("/api/v1/auth/api-keys")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "my-key"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_delete_api_key(self, client, mocker):
        mock_user = mocker.MagicMock()
        mock_user.id = 1
        mock_user.is_active = True
        mock_user.is_superuser = True

        async def _fake_user():
            return mock_user

        mock_key_obj = mocker.MagicMock()
        mock_key_obj.id = 1
        mock_key_obj.user_id = 1
        mock_key_obj.name = "my-key"

        from app.api.deps import get_current_user, get_db
        from app.main import app

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        mocker.patch("app.crud.api_key.CRUDApiKey.get", return_value=mock_key_obj)
        mocker.patch("app.crud.api_key.CRUDApiKey.delete", return_value=None)

        try:
            resp = client.delete("/api/v1/auth/api-keys/1")
            assert resp.status_code == 204
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
