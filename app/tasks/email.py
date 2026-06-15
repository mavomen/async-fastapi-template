"""Email notification task."""

import time

from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.tasks.base import BaseTask

logger = get_task_logger(__name__)


@celery_app.task(
    bind=True,
    base=BaseTask,
    max_retries=3,
    autoretry_for=(Exception,),
    default_retry_delay=60,
)
def send_email_notification(self, recipient: str, subject: str, body: str) -> dict:
    logger.info(f"Sending email to {recipient}: {subject}")
    time.sleep(2)  # simulate sending
    return {"status": "sent", "recipient": recipient, "subject": subject}
