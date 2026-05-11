"""Tests for RLS tenant filter on UPDATE and DELETE."""

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.sql import delete, update

from app.core.database import apply_tenant_filter

metadata = MetaData()
table = Table("test", metadata, Column("tenant_id", Integer), Column("name", String))


def test_rls_update_adds_where_with_tenant():
    clause = update(table).values(name="new")
    result, _, _ = apply_tenant_filter(42, clause, [], {}, {})
    assert "WHERE" in str(result)


def test_rls_delete_adds_where_with_tenant():
    clause = delete(table)
    result, _, _ = apply_tenant_filter(42, clause, [], {}, {})
    assert "WHERE" in str(result)
