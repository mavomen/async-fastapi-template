"""Tests for Celery application configuration."""


from app.core.config import settings


def test_celery_app_broker_url():
    from app.core.celery_app import celery_app

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL
    assert celery_app.conf.result_backend == settings.CELERY_RESULT_BACKEND


def test_celery_app_has_expected_config():
    from app.core.celery_app import celery_app

    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_track_started is True


def test_celery_app_module_imports():
    import importlib

    import app.core.celery_app

    importlib.reload(app.core.celery_app)

    assert app.core.celery_app.celery_app is not None
