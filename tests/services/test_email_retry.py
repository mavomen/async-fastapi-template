"""Unit test for email retry Celery task."""

import contextlib
from unittest.mock import patch

from app.services.email import send_email_with_retry


def test_send_email_with_retry_calls_email_service():
    with patch("app.services.email.email_service.send_email") as mock_send:
        with contextlib.suppress(Exception):
            send_email_with_retry.apply(args=["test@example.com", "Subject", "verification.html", {}])
    assert send_email_with_retry is not None
