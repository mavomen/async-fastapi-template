"""API endpoints for managing outgoing webhooks."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.events.base import Event
from app.identity.auth.permissions import PermissionChecker
from app.identity.models.user import User
from app.notifications.crud.webhook import webhook as crud_webhook
from app.notifications.models.webhook import Webhook
from app.notifications.schemas.webhook import (
    WebhookCreate,
    WebhookCreated,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
)

router = APIRouter()


def _get_owned_webhook(webhook_obj: Webhook | None, current_user: User) -> Webhook:
    """Return the webhook if the user may access it, else 404."""
    if webhook_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    if (
        not current_user.is_superuser
        and webhook_obj.tenant_id is not None
        and webhook_obj.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return webhook_obj


@router.post(
    "",
    response_model=WebhookCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Register an outgoing webhook. The HMAC signing secret is returned only once.",
)
async def create_webhook(
    *,
    db: AsyncSession = Depends(get_db),
    obj_in: WebhookCreate,
    current_user: User = Depends(PermissionChecker(["webhook:write"])),
) -> Any:
    webhook_obj, secret = await crud_webhook.create_with_secret(db, obj_in=obj_in)
    return WebhookCreated(
        id=webhook_obj.id,
        name=webhook_obj.name,
        url=webhook_obj.url,
        event_types=webhook_obj.event_types,
        is_active=webhook_obj.is_active,
        last_delivery_at=webhook_obj.last_delivery_at,
        last_status=webhook_obj.last_status,
        failure_count=webhook_obj.failure_count,
        created_at=webhook_obj.created_at,
        updated_at=webhook_obj.updated_at,
        secret=secret,
    )


@router.get(
    "",
    response_model=list[WebhookResponse],
    summary="List webhooks",
    description="List webhooks for the current tenant (all when superuser).",
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    tenant_id = None if current_user.is_superuser else current_user.tenant_id
    return await crud_webhook.list_for_tenant(db, tenant_id=tenant_id)


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Get webhook",
    description="Fetch a single webhook by ID.",
)
async def get_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    webhook_obj = await crud_webhook.get(db, id=webhook_id)
    return _get_owned_webhook(webhook_obj, current_user)


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    summary="Update webhook",
    description="Update name, URL, event subscriptions, or active status.",
)
async def update_webhook(
    webhook_id: int,
    *,
    db: AsyncSession = Depends(get_db),
    obj_in: WebhookUpdate,
    current_user: User = Depends(PermissionChecker(["webhook:write"])),
) -> Any:
    webhook_obj = await crud_webhook.get(db, id=webhook_id)
    webhook_obj = _get_owned_webhook(webhook_obj, current_user)
    result = await crud_webhook.update(db, db_obj=webhook_obj, obj_in=obj_in)
    return result


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete webhook",
    description="Delete (soft-delete) a webhook and its delivery history.",
)
async def delete_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["webhook:write"])),
) -> None:
    webhook_obj = await crud_webhook.get(db, id=webhook_id)
    _get_owned_webhook(webhook_obj, current_user)
    await crud_webhook.delete(db, id=webhook_id)


@router.post(
    "/{webhook_id}/restore",
    response_model=WebhookResponse,
    summary="Restore webhook",
    description="Restore a soft-deleted webhook.",
)
async def restore_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["webhook:write"])),
) -> Any:
    webhook_obj = await crud_webhook.restore(db, id=webhook_id)
    return _get_owned_webhook(webhook_obj, current_user)


@router.post(
    "/{webhook_id}/ping",
    response_model=WebhookDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send test webhook",
    description="Enqueue a synthetic test event to the webhook endpoint.",
)
async def ping_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["webhook:write"])),
) -> Any:
    webhook_obj = await crud_webhook.get(db, id=webhook_id)
    webhook_obj = _get_owned_webhook(webhook_obj, current_user)
    event = Event(
        event_type="webhook.test",
        payload={"message": "ping", "webhook_id": webhook_obj.id},
    )
    delivery = await crud_webhook.create_delivery(
        db,
        webhook_id=webhook_obj.id,
        event=event,
        max_attempts=settings.WEBHOOK_MAX_RETRIES + 1,
    )
    from app.notifications.tasks.webhook import deliver_webhook

    deliver_webhook.delay(delivery.id)
    return delivery


@router.get(
    "/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    summary="Webhook delivery history",
    description="List delivery attempts for a webhook.",
)
async def list_deliveries(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    webhook_obj = await crud_webhook.get(db, id=webhook_id)
    webhook_obj = _get_owned_webhook(webhook_obj, current_user)
    return await crud_webhook.list_deliveries(db, webhook_id=webhook_id)
