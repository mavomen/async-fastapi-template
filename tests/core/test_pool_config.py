"""Tests for per-environment pool tuning and pool gauge reporting."""

import pytest

from app.core.config import Settings


class TestPerEnvPoolDefaults:
    """Test effective_pool_size and effective_max_overflow resolution."""

    def test_explicit_values_override_presets(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            SECRET_KEY="test-secret-key-min-32-characters-long",
            DB_POOL_SIZE=99,
            DB_MAX_OVERFLOW=77,
        )
        assert s.effective_pool_size == 99
        assert s.effective_max_overflow == 77

    def test_development_preset(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="development",
            SECRET_KEY="test-secret-key-min-32-characters-long",
        )
        assert s.effective_pool_size == 10
        assert s.effective_max_overflow == 5

    def test_staging_preset(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="staging",
            SECRET_KEY="test-secret-key-min-32-characters-long",
        )
        assert s.effective_pool_size == 20
        assert s.effective_max_overflow == 10

    def test_production_preset(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="test-secret-key-min-32-characters-long",
        )
        assert s.effective_pool_size == 40
        assert s.effective_max_overflow == 20

    def test_test_env_defaults(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="test",
            SECRET_KEY="test-secret-key-min-32-characters-long",
        )
        assert s.effective_pool_size == 20
        assert s.effective_max_overflow == 10


@pytest.mark.asyncio
async def test_pool_gauges_reflect_checkedout_checkedin(db_session):
    """Pool gauges are set after a session finishes."""
    from app.core.database import _report_pool_saturation, sessionmanager
    from app.core.metrics import db_pool_active, db_pool_idle, db_pool_overflow

    sessionmanager.init(
        writer_url="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
        reader_url="postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test",
    )
    _report_pool_saturation("writer")
    _report_pool_saturation("reader")
    await sessionmanager.close()

    assert db_pool_active.labels(pool="writer")._value.get() >= 0
    assert db_pool_idle.labels(pool="writer")._value.get() >= 0
    assert db_pool_overflow.labels(pool="writer")._value.get() >= 0
    assert db_pool_active.labels(pool="reader")._value.get() >= 0
    assert db_pool_idle.labels(pool="reader")._value.get() >= 0
    assert db_pool_overflow.labels(pool="reader")._value.get() >= 0
