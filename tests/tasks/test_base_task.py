"""Unit tests for Celery base task."""

from unittest.mock import patch

from app.tasks.base import BaseTask


def test_base_task_on_failure():
    task = BaseTask()
    with patch.object(task, "_update_status") as mock_update:
        task.on_failure(exc=ValueError("err"), task_id="abc", _args=[], _kwargs={}, _einfo=None)
        mock_update.assert_called_once_with("abc", "FAILURE", "err")


def test_base_task_on_success():
    task = BaseTask()
    with patch.object(task, "_update_status") as mock_update:
        task.on_success(_retval="done", task_id="xyz", _args=[], _kwargs={})
        mock_update.assert_called_once_with("xyz", "SUCCESS")
