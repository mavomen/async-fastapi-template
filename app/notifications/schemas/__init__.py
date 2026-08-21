"""Notifications domain Pydantic schemas."""

from app.notifications.schemas.notification import (
    NotificationCreate,
    NotificationCursorResponse,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    NotificationTestRequest,
    NotificationUpdate,
)
from app.notifications.schemas.webhook import (
    WebhookCreate,
    WebhookCreated,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
)

__all__ = [
    "NotificationCreate",
    "NotificationCursorResponse",
    "NotificationListResponse",
    "NotificationPreferenceResponse",
    "NotificationPreferenceUpdate",
    "NotificationResponse",
    "NotificationTestRequest",
    "NotificationUpdate",
    "WebhookCreate",
    "WebhookCreated",
    "WebhookDeliveryResponse",
    "WebhookResponse",
    "WebhookUpdate",
]
