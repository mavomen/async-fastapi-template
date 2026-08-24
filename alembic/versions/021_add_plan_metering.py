"""add metering config to plans

Revision ID: 021_add_plan_metering
Revises: 020_add_invoicing
Create Date: 2026-08-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "021_add_plan_metering"
down_revision: str | None = "020_add_invoicing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("metering", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "metering")
