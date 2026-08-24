"""add dunning state to subscriptions

Revision ID: 022_add_dunning
Revises: 021_add_plan_metering
Create Date: 2026-08-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022_add_dunning"
down_revision: str | None = "021_add_plan_metering"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("failed_payment_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("last_payment_failure_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "suspended_at")
    op.drop_column("subscriptions", "next_retry_at")
    op.drop_column("subscriptions", "last_payment_failure_at")
    op.drop_column("subscriptions", "failed_payment_count")
