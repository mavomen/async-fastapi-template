"""Base Celery task with error handling and status tracking."""

from typing import Any

from celery import Task
from celery.utils.log import get_task_logger

from app.core.config import settings
from app.tasks.status import update_task_status

logger = get_task_logger(__name__)


class BaseTask(Task):  # type: ignore[misc]
    """Celery base task that automatically tracks status."""

    abstract = True

    def on_failure(
        self, exc: Any, task_id: str, _args: tuple[Any, ...], _kwargs: dict[str, Any], _einfo: Any
    ) -> None:
        logger.warning(f"Task {task_id} failed after retries: {exc}")
        self._update_status(task_id, "FAILURE", str(exc))

    def on_success(
        self, _retval: Any, task_id: str, _args: tuple[Any, ...], _kwargs: dict[str, Any]
    ) -> None:
        self._update_status(task_id, "SUCCESS")

    def _update_status(self, task_id: str, status: str, error: str | None = None) -> None:
        import asyncio

        from app.core.database import sessionmanager

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _update() -> None:
            if sessionmanager._engine is None:
                sessionmanager.init(settings.DATABASE_URL)
            async with sessionmanager.session() as db:
                await update_task_status(db, task_id, status, error)

        loop.run_until_complete(_update())
