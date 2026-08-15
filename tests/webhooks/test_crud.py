"""Tests for webhook CRUD operations."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.events.base import Event
from app.schemas.webhook import WebhookCreate


class TestCRUDWebhook:
    @pytest.mark.asyncio
    async def test_create_with_secret(self):
        db = AsyncMock()
        obj_in = WebhookCreate(name="my webhook", url="https://example.com/hook")

        from app.crud.webhook import webhook as crud

        webhook_obj, secret = await crud.create_with_secret(db, obj_in=obj_in)

        assert webhook_obj.name == "my webhook"
        assert webhook_obj.url == "https://example.com/hook"
        assert webhook_obj.secret == secret
        assert webhook_obj.event_types is None
        assert secret
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_with_secret_keeps_event_types(self):
        db = AsyncMock()
        obj_in = WebhookCreate(
            name="scoped", url="https://example.com/hook", event_types=["user.created"]
        )

        from app.crud.webhook import webhook as crud

        webhook_obj, _ = await crud.create_with_secret(db, obj_in=obj_in)
        assert webhook_obj.event_types == ["user.created"]

    @pytest.mark.asyncio
    async def test_get_active_for_event_type_exact_match(self):
        w1 = SimpleNamespace(is_active=True, event_types=["user.created"])
        w2 = SimpleNamespace(is_active=True, event_types=["order.placed"])
        w3 = SimpleNamespace(is_active=True, event_types=None)
        w4 = SimpleNamespace(is_active=True, event_types=[])

        result = MagicMock()
        result.scalars.return_value.all.return_value = [w1, w2, w3, w4]
        db = AsyncMock()
        db.execute.return_value = result

        from app.crud.webhook import webhook as crud

        matched = await crud.get_active_for_event_type(db, event_type="user.created")
        assert matched == [w1, w3, w4]

    @pytest.mark.asyncio
    async def test_create_delivery(self):
        db = AsyncMock()
        event = Event(event_type="user.created", payload={"id": 1})

        from app.crud.webhook import webhook as crud

        delivery = await crud.create_delivery(db, webhook_id=3, event=event, max_attempts=6)

        assert delivery.webhook_id == 3
        assert delivery.event_id == event.id
        assert delivery.event_type == "user.created"
        assert delivery.payload == {"id": 1}
        assert delivery.attempt == 0
        assert delivery.max_attempts == 6
        assert delivery.status == "pending"

    @pytest.mark.asyncio
    async def test_get_delivery_with_webhook(self):
        db = AsyncMock()
        result = MagicMock()
        result.first.return_value = (object(), object())
        db.execute.return_value = result

        from app.crud.webhook import webhook as crud

        pair = await crud.get_delivery_with_webhook(db, delivery_id=1)
        assert pair is not None
        assert len(pair) == 2

    @pytest.mark.asyncio
    async def test_get_delivery_with_webhook_missing(self):
        db = AsyncMock()
        result = MagicMock()
        result.first.return_value = None
        db.execute.return_value = result

        from app.crud.webhook import webhook as crud

        assert await crud.get_delivery_with_webhook(db, delivery_id=1) is None

    @pytest.mark.asyncio
    async def test_list_deliveries(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [SimpleNamespace(id=1)]
        db = AsyncMock()
        db.execute.return_value = result

        from app.crud.webhook import webhook as crud

        rows = await crud.list_deliveries(db, webhook_id=3)
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_list_for_tenant_filters(self):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [SimpleNamespace(id=1)]
        db = AsyncMock()
        db.execute.return_value = result

        from app.crud.webhook import webhook as crud

        rows = await crud.list_for_tenant(db, tenant_id=5)
        assert len(rows) == 1
