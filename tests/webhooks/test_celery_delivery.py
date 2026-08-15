"""Tests for the Celery webhook delivery task."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest

from app.tasks.webhook import deliver_webhook


def _delivery(attempt=0, max_attempts=3, status="pending"):
    return SimpleNamespace(
        id=5,
        webhook_id=1,
        event_id="evt-001",
        event_type="user.created",
        payload={"id": 1},
        attempt=attempt,
        max_attempts=max_attempts,
        status=status,
        created_at=datetime.now(UTC),
    )


def _webhook(secret="secret", is_active=True):
    return SimpleNamespace(secret=secret, is_active=is_active, url="https://example.com/hook")


def run_coro(coro):
    """Run a coroutine on a fresh event loop (the pytest loop is busy)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPerformDelivery:
    def _patch(self, mocker, response):
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response
        mocker.patch("app.tasks.webhook.httpx.Client", return_value=client)
        mocker.patch("app.tasks.webhook._run_async", Mock(side_effect=run_coro))
        record = AsyncMock()
        mocker.patch("app.tasks.webhook._record_delivery_outcome", record)
        return client, record

    def test_success(self, mocker):
        from app.tasks.webhook import _perform_delivery

        response = Mock(status_code=200, text="ok")
        client, record = self._patch(mocker, response)
        result = _perform_delivery(_delivery(), _webhook())

        assert result == "delivered"
        client.post.assert_called_once()
        args, kwargs = client.post.call_args
        assert kwargs["headers"]["X-Webhook-Event"] == "user.created"
        assert kwargs["headers"]["X-Webhook-Delivery"] == "5"
        assert kwargs["headers"]["X-Webhook-Attempt"] == "1"
        signature = kwargs["headers"]["X-Webhook-Signature"]
        assert signature.startswith("t=")
        assert "v1=" in signature
        record.assert_awaited_once()
        outcome = record.await_args.kwargs["outcome"]
        assert outcome["status"] == "delivered"
        assert outcome["response_status"] == 200

    def test_non_2xx_with_retries_left(self, mocker):
        from app.tasks.webhook import _perform_delivery

        response = Mock(status_code=500, text="boom")
        client, record = self._patch(mocker, response)
        result = _perform_delivery(_delivery(attempt=0, max_attempts=3), _webhook())

        assert result == "retry"
        outcome = record.await_args.kwargs["outcome"]
        assert outcome["status"] == "retrying"
        assert outcome["error"] == "HTTP 500"
        assert outcome["response_status"] == 500
        assert outcome["next_retry_at"] is not None
        assert outcome["next_retry_at"] > datetime.now(UTC)

    def test_non_2xx_final_failure(self, mocker):
        from app.tasks.webhook import _perform_delivery

        response = Mock(status_code=500, text="boom")
        self._patch(mocker, response)
        result = _perform_delivery(_delivery(attempt=2, max_attempts=3), _webhook())

        assert result == "failed"

    def test_http_error_retries(self, mocker):
        from app.tasks.webhook import _perform_delivery

        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = httpx.ConnectError("connection refused")
        mocker.patch("app.tasks.webhook.httpx.Client", return_value=client)
        mocker.patch("app.tasks.webhook._run_async", Mock(side_effect=run_coro))
        record = AsyncMock()
        mocker.patch("app.tasks.webhook._record_delivery_outcome", record)

        result = _perform_delivery(_delivery(attempt=0, max_attempts=3), _webhook())
        assert result == "retry"
        assert record.await_args.kwargs["outcome"]["status"] == "retrying"
        assert "connection refused" in record.await_args.kwargs["outcome"]["error"]

    def test_http_error_final_failure(self, mocker):
        from app.tasks.webhook import _perform_delivery

        client = MagicMock()
        client.__enter__.return_value = client
        client.post.side_effect = httpx.ConnectError("connection refused")
        mocker.patch("app.tasks.webhook.httpx.Client", return_value=client)
        mocker.patch("app.tasks.webhook._run_async", Mock(side_effect=run_coro))
        record = AsyncMock()
        mocker.patch("app.tasks.webhook._record_delivery_outcome", record)

        result = _perform_delivery(_delivery(attempt=2, max_attempts=3), _webhook())
        assert result == "failed"
        assert record.await_args.kwargs["outcome"]["status"] == "failed"


class TestDeliverWebhookTask:
    def test_not_found(self, mocker):
        mocker.patch("app.tasks.webhook._run_async", Mock(return_value=None))
        assert deliver_webhook.run(99) == "not-found"

    def test_already_delivered(self, mocker):
        mocker.patch(
            "app.tasks.webhook._run_async",
            Mock(return_value=(_delivery(status="delivered"), _webhook())),
        )
        assert deliver_webhook.run(5) == "already-delivered"

    def test_webhook_disabled(self, mocker):
        mocker.patch(
            "app.tasks.webhook._run_async",
            Mock(return_value=(_delivery(), _webhook(is_active=False))),
        )
        mocker.patch("app.tasks.webhook._record_delivery_outcome", AsyncMock())
        assert deliver_webhook.run(5) == "webhook-disabled"

    def test_retry_raises_celery_retry(self, mocker):
        mocker.patch(
            "app.tasks.webhook._run_async",
            Mock(return_value=(_delivery(attempt=0, max_attempts=3), _webhook())),
        )
        mocker.patch("app.tasks.webhook._perform_delivery", Mock(return_value="retry"))

        class RetrySentinel(Exception):
            pass

        retry_mock = Mock(side_effect=RetrySentinel)
        mocker.patch.object(deliver_webhook, "retry", retry_mock)

        with pytest.raises(RetrySentinel):
            deliver_webhook.run(5)
        retry_mock.assert_called_once()

    def test_perform_failure_propagates_status(self, mocker):
        mocker.patch(
            "app.tasks.webhook._run_async",
            Mock(return_value=(_delivery(), _webhook())),
        )
        mocker.patch("app.tasks.webhook._perform_delivery", Mock(return_value="failed"))
        assert deliver_webhook.run(5) == "failed"
