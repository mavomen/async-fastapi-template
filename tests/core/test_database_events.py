"""Unit tests for Row-Level Security event filter."""

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.sql import delete, insert, select, update

from app.core.database import apply_tenant_filter

metadata = MetaData()

sample_table = Table(
    "sample",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("tenant_id", Integer, nullable=True),
    Column("name", String),
)


def test_rls_select_no_tenant():
    """When tenant_id is None, no WHERE clause is added."""
    clause = select(sample_table)
    result, _, _ = apply_tenant_filter(None, clause, [], {}, {})
    assert "WHERE" not in str(result)


def test_rls_select_with_tenant():
    """When a tenant is active, WHERE tenant_id is added."""
    clause = select(sample_table)
    result, _, _ = apply_tenant_filter(42, clause, [], {}, {})
    assert "WHERE" in str(result)


def test_rls_insert_sets_tenant_id():
    """INSERT statements get tenant_id added automatically."""
    clause = insert(sample_table).values(name="test")
    result, _, _ = apply_tenant_filter(7, clause, [], {}, {})
    assert "tenant_id" in str(result)


def test_rls_update_adds_where():
    """UPDATE statements get a WHERE tenant_id clause."""
    clause = update(sample_table).values(name="new")
    result, _, _ = apply_tenant_filter(3, clause, [], {}, {})
    assert "WHERE" in str(result)


def test_rls_delete_adds_where():
    """DELETE statements get a WHERE tenant_id clause."""
    clause = delete(sample_table)
    result, _, _ = apply_tenant_filter(3, clause, [], {}, {})
    assert "WHERE" in str(result)
