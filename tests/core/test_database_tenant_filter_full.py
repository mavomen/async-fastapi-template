"""Cover tenant-filter branches not hit by previous tests."""

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.sql import delete, insert, update

from app.core.database import apply_tenant_filter

metadata = MetaData()
tbl = Table("sample", metadata, Column("tenant_id", Integer), Column("name", String))


def test_rls_insert_no_tenant_column():
    """Table without tenant_id should not be modified."""
    t = Table("plain", metadata, Column("id", Integer))
    clause = insert(t).values(id=1)
    result, _, _ = apply_tenant_filter(1, clause, [], {}, {})
    assert "tenant_id" not in str(result)


def test_rls_update_without_tenant_id_column():
    """Update on a table without tenant_id should be passed through."""
    t = Table("plain2", metadata, Column("name", String))
    clause = update(t).values(name="new")
    result, _, _ = apply_tenant_filter(1, clause, [], {}, {})
    assert "WHERE" not in str(result)


def test_rls_delete_without_tenant_id_column():
    """Delete on a table without tenant_id should be passed through."""
    t = Table("plain3", metadata, Column("name", String))
    clause = delete(t)
    result, _, _ = apply_tenant_filter(1, clause, [], {}, {})
    assert "WHERE" not in str(result)
