"""Tests for email retry with exponential backoff."""


def test_send_email_with_retry_registered():
    """Verify the Celery task is registered and callable."""
    from app.notifications.services.email import send_email_with_retry

    assert send_email_with_retry is not None
    assert callable(send_email_with_retry.delay)
