"""add oauth fields to users table

Revision ID: 012_add_oauth_fields
Revises: 011_add_totp_fields
Create Date: 2026-07-01 06:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_add_oauth_fields"
down_revision: str | None = "011_add_totp_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("oauth_provider_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("oauth_access_token", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("oauth_refresh_token", sa.String(512), nullable=True))
    op.create_index("ix_users_oauth_provider_id", "users", ["oauth_provider", "oauth_provider_id"])


def downgrade() -> None:
    op.drop_index("ix_users_oauth_provider_id", table_name="users")
    op.drop_column("users", "oauth_refresh_token")
    op.drop_column("users", "oauth_access_token")
    op.drop_column("users", "oauth_provider_id")
    op.drop_column("users", "oauth_provider")
