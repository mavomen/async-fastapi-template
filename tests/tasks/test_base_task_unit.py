"""Unit tests for Celery base task callbacks."""

from unittest.mock import patch

from app.tasks.base import BaseTask


def test_on_failure_calls_update():
    task = BaseTask()
    with patch.object(task, "_update_status") as mock:
        task.on_failure(ValueError("boom"), "task-1", _args=(), _kwargs={}, _einfo=None)
        mock.assert_called_once_with("task-1", "FAILURE", "boom")


def test_on_success_calls_update():
    task = BaseTask()
    with patch.object(task, "_update_status") as mock:
        task.on_success(_retval="result", task_id="task-2", _args=(), _kwargs={})
        mock.assert_called_once_with("task-2", "SUCCESS")
