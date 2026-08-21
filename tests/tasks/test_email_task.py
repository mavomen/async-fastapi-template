"""Test for email Celery task existence."""

from app.notifications.tasks.email import send_email_notification


def test_email_task_registered():
    assert send_email_notification is not None
    assert hasattr(send_email_notification, "delay")
