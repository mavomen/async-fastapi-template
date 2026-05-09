"""add search vector and audit logs

Revision ID: 005_add_search_and_audit
Revises: 004_add_tenants
Create Date: 2026-05-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_add_search_and_audit"
down_revision: str | None = "004_add_tenants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Audit logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("changed_fields", sa.String(), nullable=True),
        sa.Column("old_values", sa.String(), nullable=True),
        sa.Column("new_values", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add full‑text search vector to users
    op.add_column(
        "users",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(
        "UPDATE users SET search_vector = to_tsvector('english', coalesce(email, '') || ' ' || coalesce(username, '') || ' ' || coalesce(full_name, ''))"
    )
    op.execute("CREATE INDEX ix_users_search_vector ON users USING gin(search_vector)")
    op.execute("""
        CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
        ON users FOR EACH ROW EXECUTE FUNCTION
        tsvector_update_trigger(search_vector, 'pg_catalog.english', email, username, full_name)
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tsvectorupdate ON users")
    op.drop_index("ix_users_search_vector", table_name="users")
    op.drop_column("users", "search_vector")
    op.drop_table("audit_logs")
