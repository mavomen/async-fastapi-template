"""CRUD operations for outgoing webhooks."""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.events.base import Event
from app.models.webhook import Webhook, WebhookDelivery
from app.schemas.webhook import WebhookCreate, WebhookUpdate


class CRUDWebhook(CRUDBase[Webhook, WebhookCreate, WebhookUpdate]):
    async def create_with_secret(
        self, db: AsyncSession, *, obj_in: WebhookCreate
    ) -> tuple[Webhook, str]:
        """Create a webhook and generate a fresh HMAC signing secret.

        The secret is returned only from this call — it is never exposed again.
        """
        secret = secrets.token_urlsafe(32)
        db_obj = Webhook(
            name=obj_in.name,
            url=str(obj_in.url),
            secret=secret,
            event_types=obj_in.event_types,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj, secret

    async def get_active_for_event_type(
        self, db: AsyncSession, *, event_type: str
    ) -> list[Webhook]:
        """Return active webhooks subscribed to the given event type.

        A webhook with no/empty ``event_types`` is subscribed to all events.
        """
        result = await db.execute(select(Webhook).where(Webhook.is_active.is_(True)))
        webhooks = list(result.scalars().all())
        return [
            webhook
            for webhook in webhooks
            if not webhook.event_types or event_type in webhook.event_types
        ]

    async def list_for_tenant(
        self, db: AsyncSession, *, tenant_id: int | None, skip: int = 0, limit: int = 100
    ) -> list[Webhook]:
        query = select(Webhook).order_by(Webhook.id.desc()).offset(skip).limit(limit)
        if tenant_id is not None:
            query = query.where(Webhook.tenant_id == tenant_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_delivery(
        self,
        db: AsyncSession,
        *,
        webhook_id: int,
        event: Event,
        max_attempts: int,
    ) -> WebhookDelivery:
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_id=event.id,
            event_type=event.event_type,
            payload=event.payload,
            attempt=0,
            max_attempts=max_attempts,
            status="pending",
        )
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)
        return delivery

    async def get_delivery(self, db: AsyncSession, *, delivery_id: int) -> WebhookDelivery | None:
        result = await db.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        return result.scalar_one_or_none()

    async def get_delivery_with_webhook(
        self, db: AsyncSession, *, delivery_id: int
    ) -> tuple[WebhookDelivery, Webhook] | None:
        result = await db.execute(
            select(WebhookDelivery, Webhook)
            .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
            .where(WebhookDelivery.id == delivery_id)
        )
        row = result.first()
        if row is None:
            return None
        return row[0], row[1]

    async def list_deliveries(
        self,
        db: AsyncSession,
        *,
        webhook_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        result = await db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


webhook = CRUDWebhook(Webhook)
