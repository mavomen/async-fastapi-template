"""Tests for soft-delete functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.identity.models.api_key import ApiKey
from app.identity.models.tenant import Tenant
from app.identity.models.user import User
from app.identity.schemas.api_key import ApiKeyResponse
from app.identity.schemas.user import PurgeResponse, UserResponse
from app.models.base import SoftDeleteMixin
from app.notifications.models.notification import Notification
from app.notifications.models.webhook import Webhook
from app.notifications.schemas.notification import NotificationResponse
from app.notifications.schemas.webhook import WebhookResponse


class _SoftDeleteStub(SoftDeleteMixin):
    """Minimal stub that passes _has_soft_delete via MRO."""

    deleted_at: datetime | None = None


class _NoSoftDeleteStub:
    pass


class TestSoftDeleteMixin:
    def test_has_soft_delete_true(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(User) is True

    def test_has_soft_delete_false_for_non_mixin(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(Tenant) is False

    def test_mixin_in_mro(self):
        assert SoftDeleteMixin in User.__mro__

    def test_notification_has_mixin(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(Notification) is True

    def test_webhook_has_mixin(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(Webhook) is True

    def test_api_key_has_mixin(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(ApiKey) is True

    def test_stub_has_soft_delete(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(_SoftDeleteStub) is True

    def test_stub_no_soft_delete(self):
        from app.crud.base import _has_soft_delete

        assert _has_soft_delete(_NoSoftDeleteStub) is False


class TestCRUDSoftDelete:
    @pytest.mark.asyncio
    async def test_delete_sets_deleted_at(self):
        from app.crud.base import CRUDBase

        crud = CRUDBase(_SoftDeleteStub)
        stub = _SoftDeleteStub()
        stub.id = 1
        stub.deleted_at = None
        crud.get = AsyncMock(return_value=stub)

        mock_session = AsyncMock()
        result = await crud.delete(mock_session, id=1)

        assert result is not None
        assert result.deleted_at is not None
        mock_session.add.assert_called_once_with(stub)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_returns_none_when_not_found(self):
        from app.crud.base import CRUDBase

        crud = CRUDBase(_SoftDeleteStub)
        crud.get = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        result = await crud.delete(mock_session, id=999)

        assert result is None
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_restore_clears_deleted_at(self):
        from app.crud.base import CRUDBase

        crud = CRUDBase(_SoftDeleteStub)
        stub = _SoftDeleteStub()
        stub.id = 1
        stub.deleted_at = datetime.now(UTC)
        crud.get = AsyncMock(return_value=stub)

        mock_session = AsyncMock()
        result = await crud.restore(mock_session, id=1)

        assert result is not None
        assert result.deleted_at is None
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_restore_returns_none_for_active_record(self):
        from app.crud.base import CRUDBase

        crud = CRUDBase(_SoftDeleteStub)
        stub = _SoftDeleteStub()
        stub.id = 1
        stub.deleted_at = None
        crud.get = AsyncMock(return_value=stub)

        mock_session = AsyncMock()
        result = await crud.restore(mock_session, id=1)

        assert result is None
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_purge_removes_old_deleted_records(self):
        from unittest.mock import patch

        from app.crud.base import CRUDBase

        crud = CRUDBase(User)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.crud.base._has_soft_delete", return_value=True):
            count = await crud.purge(mock_session, older_than_days=90)

        assert count == 5
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_purge_returns_zero_for_non_soft_delete_model(self):
        from app.crud.base import CRUDBase

        crud = CRUDBase(_NoSoftDeleteStub)
        mock_session = AsyncMock()

        count = await crud.purge(mock_session, older_than_days=90)

        assert count == 0


class TestSoftDeleteSchemas:
    def test_purge_response_schema(self):
        resp = PurgeResponse(purged_count=3)
        assert resp.purged_count == 3

    def test_response_schemas_include_deleted_at(self) -> None:
        for schema_cls in [UserResponse, NotificationResponse, WebhookResponse, ApiKeyResponse]:
            fields = schema_cls.model_fields
            assert "deleted_at" in fields
            assert fields["deleted_at"].default is None
