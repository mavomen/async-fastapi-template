"""add soft-delete support (deleted_at column)

Revision ID: 015_add_soft_delete
Revises: 014_add_notifications
Create Date: 2026-08-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_add_soft_delete"
down_revision: str | None = "014_add_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = ["users", "notifications", "webhooks", "api_keys"]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            f"ix_{table}_deleted_at",
            table,
            ["deleted_at"],
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_deleted_at", table_name=table)
        op.drop_column(table, "deleted_at")
