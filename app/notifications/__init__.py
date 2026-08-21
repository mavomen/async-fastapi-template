"""Notifications bounded context.

Owns the in-app inbox, per-user notification preferences, transactional
email delivery (Jinja2 templates in app/templates/email/), and outgoing
webhooks with HMAC signing, retries, and preference-gated dispatch.
"""

from app.notifications.models.notification import Notification
from app.notifications.models.notification_preference import NotificationPreference
from app.notifications.models.webhook import Webhook, WebhookDelivery

__all__ = ["Notification", "NotificationPreference", "Webhook", "WebhookDelivery"]
