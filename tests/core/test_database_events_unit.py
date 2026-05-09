"""Edge case tests for RLS tenant filter."""

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.sql import insert, update, delete
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
