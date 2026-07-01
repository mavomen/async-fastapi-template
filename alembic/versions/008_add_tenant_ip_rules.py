"""add tenant ip rules table

Revision ID: 008_add_tenant_ip_rules
Revises: 007_add_lockout_fields
Create Date: 2026-06-29 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_add_tenant_ip_rules"
down_revision: str | None = "007_add_lockout_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_ip_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("ip_or_cidr", sa.String(45), nullable=False),
        sa.Column("action", sa.Enum("allow", "deny", name="ip_rule_action"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(255), nullable=True),
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


def downgrade() -> None:
    op.drop_table("tenant_ip_rules")
    op.execute("DROP TYPE IF EXISTS ip_rule_action")
