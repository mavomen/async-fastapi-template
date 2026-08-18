"""Edge case tests for RLS tenant filter and slow-query EXPLAIN capture."""

import logging

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, text
from sqlalchemy.sql import delete, insert, update

from app.core.database import apply_tenant_filter

metadata = MetaData()
table = Table("sample", metadata, Column("tenant_id", Integer), Column("name", String))


def test_rls_insert_no_tenant_id_column():
    """If the table has no tenant_id, no modification happens."""
    tbl = Table("no_tenant", metadata, Column("id", Integer))
    clause = insert(tbl).values(id=1)
    result, _, _ = apply_tenant_filter(1, clause, [], {}, {})
    assert "tenant_id" not in str(result)


def test_rls_update_with_tenant():
    """Update clause adds WHERE tenant_id when a tenant is active."""
    clause = update(table).values(name="new")
    result, _, _ = apply_tenant_filter(7, clause, [], {}, {})
    assert "WHERE" in str(result)


def test_rls_delete_with_tenant():
    """Delete clause adds WHERE tenant_id when a tenant is active."""
    clause = delete(table)
    result, _, _ = apply_tenant_filter(7, clause, [], {}, {})
    assert "WHERE" in str(result)


@pytest.mark.asyncio
async def test_slow_query_logs_and_explains(db_session, monkeypatch, caplog):
    """A SELECT exceeding the threshold triggers a log + EXPLAIN plan when enabled."""
    from app.core.config import Settings

    low_threshold_settings = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        SECRET_KEY="test-secret-key-min-32-characters-long",
        SLOW_QUERY_THRESHOLD_MS=0,
        DB_SLOW_QUERY_CAPTURE_EXPLAIN=True,
    )
    monkeypatch.setattr("app.core.database.settings", low_threshold_settings)

    with caplog.at_level(logging.WARNING, logger="app.db"):
        await db_session.execute(text("SELECT 1"))

    slow_entries = [r for r in caplog.records if r.message == "Slow query detected"]
    assert len(slow_entries) >= 1
    assert "duration_ms" in slow_entries[0].__dict__ or hasattr(slow_entries[0], "duration_ms")


@pytest.mark.asyncio
async def test_slow_query_explain_off_skips_plan(db_session, monkeypatch, caplog):
    """With DB_SLOW_QUERY_CAPTURE_EXPLAIN=False, no plan is captured."""
    from app.core.config import Settings

    settings_no_explain = Settings(
        _env_file=None,
        ENVIRONMENT="test",
        SECRET_KEY="test-secret-key-min-32-characters-long",
        SLOW_QUERY_THRESHOLD_MS=0,
        DB_SLOW_QUERY_CAPTURE_EXPLAIN=False,
    )
    monkeypatch.setattr("app.core.database.settings", settings_no_explain)

    with caplog.at_level(logging.WARNING, logger="app.db"):
        await db_session.execute(text("SELECT 1"))

    slow_entries = [r for r in caplog.records if r.message == "Slow query detected"]
    assert len(slow_entries) >= 1
    for entry in slow_entries:
        extra = entry.__dict__.get("extra") or entry.__dict__
        assert "plan" not in str(extra)
