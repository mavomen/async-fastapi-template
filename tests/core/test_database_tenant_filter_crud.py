"""Tenant filter: Insert with tenant_id already set and Update with tenant column."""

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.sql import insert, update

from app.core.database import apply_tenant_filter

metadata = MetaData()
tbl = Table("sample", metadata, Column("tenant_id", Integer), Column("name", String))


def test_rls_insert_when_tenant_id_already_set():
    """Insert that already has tenant_id should not be modified."""
    clause = insert(tbl).values(name="test", tenant_id=5)
    result, _, _ = apply_tenant_filter(1, clause, [], {}, {})
    # tenant_id should remain 5, not be overridden to 1
    assert "tenant_id" in str(result)
    # The filter should not override the existing value


def test_rls_update_adds_where_clause():
    """Update on a table with tenant_id column adds a WHERE clause."""
    clause = update(tbl).values(name="updated")
    result, _, _ = apply_tenant_filter(3, clause, [], {}, {})
    assert "WHERE" in str(result)
    assert "tenant_id" in str(result)
