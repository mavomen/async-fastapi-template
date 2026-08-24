"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "async_fastapi_template",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "backup-database-daily": {
        "task": "app.tasks.backup.backup_database",
        "schedule": crontab(hour=2, minute=0),
    },
    "cleanup-old-backups-daily": {
        "task": "app.tasks.backup.cleanup_old_backups",
        "schedule": crontab(hour=3, minute=0),
    },
    "purge-soft-deleted-weekly": {
        "task": "app.tasks.purge.purge_soft_deleted",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday 04:00 UTC
    },
    "generate-due-invoices-daily": {
        "task": "app.tasks.invoicing.generate_due_invoices",
        "schedule": crontab(hour=5, minute=0),
    },
}
