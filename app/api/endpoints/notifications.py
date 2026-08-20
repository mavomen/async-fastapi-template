"""API endpoints for notification preferences and the in-app inbox."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_event_bus
from app.crud.notification import notification as crud_notification
from app.crud.notification import notification_preference as crud_preference
from app.events.base import Event, EventBus
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    NotificationCursorResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationTestRequest,
)
from app.utils.pagination import CursorParams, decode_cursor, encode_cursor

router = APIRouter()


@router.get(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Get notification preferences",
    description="Return the current user's per-channel notification preferences.",
)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    return await crud_preference.get_or_create(db, user_id=current_user.id)


@router.put(
    "/preferences",
    response_model=NotificationPreferenceResponse,
    summary="Update notification preferences",
    description="Opt in/out of the email, in-app, and webhook channels for this user.",
)
async def update_preferences(
    *,
    db: AsyncSession = Depends(get_db),
    obj_in: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    return await crud_preference.update_for_user(db, user_id=current_user.id, obj_in=obj_in)


@router.get(
    "",
    response_model=NotificationCursorResponse,
    summary="List notifications",
    description="List the current user's in-app notifications using cursor-based keyset pagination.",
)
async def list_notifications(
    params: CursorParams = Depends(),
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    items = await crud_notification.list_for_user_cursor(
        db, user_id=current_user.id, cursor=decode_cursor(params.cursor) if params.cursor else None,
        size=params.size, unread_only=unread_only,
    )
    has_more = len(items) > params.size
    page_items = items[: params.size]
    next_cursor = encode_cursor(page_items[-1].id) if has_more and page_items else None
    unread_count = await crud_notification.count_unread(db, user_id=current_user.id)
    return NotificationCursorResponse(
        items=page_items, next_cursor=next_cursor, has_more=has_more,
        size=len(page_items), unread_count=unread_count,
    )


def _get_owned_notification(notification_obj: Notification | None) -> Notification:
    """Return the notification if it belongs to the current user, else 404."""
    if notification_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification_obj


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
    description="Mark a single in-app notification as read.",
)
async def mark_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    notification_obj = await crud_notification.get_for_user(
        db, notification_id=notification_id, user_id=current_user.id
    )
    notification_obj = _get_owned_notification(notification_obj)
    return await crud_notification.mark_read(db, notification=notification_obj)


@router.post(
    "/read-all",
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Mark every unread in-app notification of the current user as read.",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    updated = await crud_notification.mark_all_read(db, user_id=current_user.id)
    return {"updated": updated}


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
    description="Delete (soft-delete) a single in-app notification.",
)
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    notification_obj = await crud_notification.get_for_user(
        db, notification_id=notification_id, user_id=current_user.id
    )
    _get_owned_notification(notification_obj)
    await crud_notification.delete(db, id=notification_id)


@router.post(
    "/{notification_id}/restore",
    response_model=NotificationResponse,
    summary="Restore a deleted notification",
    description="Restore a soft-deleted in-app notification.",
)
async def restore_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    notification_obj = await crud_notification.restore(db, id=notification_id)
    _get_owned_notification(notification_obj)
    return notification_obj


@router.post(
    "/test",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a test notification",
    description=(
        "Publish a synthetic notification.test event for the current user, exercising "
        "the in-app and email channels according to their preferences."
    ),
)
async def send_test_notification(
    obj_in: NotificationTestRequest = NotificationTestRequest(),
    current_user: User = Depends(get_current_user),
    bus: EventBus = Depends(get_event_bus),
) -> dict[str, Any]:
    event = Event(
        event_type="notification.test",
        payload={"title": obj_in.title, "body": obj_in.body},
        user_id=current_user.id,
    )
    await bus.publish(event)
    return {"event_id": event.id, "event_type": event.event_type}
