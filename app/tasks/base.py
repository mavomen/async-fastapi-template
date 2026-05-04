"""Base Celery task with error handling and status tracking."""

from celery import Task

from app.tasks.status import update_task_status


class BaseTask(Task):
    """Celery base task that automatically tracks status."""

    abstract = True

    def on_failure(self, exc, task_id, _args, _kwargs, _einfo):
        self._update_status(task_id, "FAILURE", str(exc))

    def on_success(self, _retval, task_id, _args, _kwargs):
        self._update_status(task_id, "SUCCESS")

    def _update_status(self, task_id: str, status: str, error: str | None = None) -> None:
        import asyncio

        from app.core.database import sessionmanager

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _update():
            sessionmanager.init(sessionmanager._engine.url)
            async with sessionmanager.session() as db:
                await update_task_status(db, task_id, status, error)

        loop.run_until_complete(_update())
