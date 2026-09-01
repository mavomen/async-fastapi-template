"""add stripe integration columns and stripe_events table

Revision ID: 019_add_stripe_integration
Revises: 018_add_billing_tables
Create Date: 2026-08-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_add_stripe_integration"
down_revision: str | None = "018_add_billing_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.create_index(
        op.f("ix_tenants_stripe_customer_id"),
        "tenants",
        ["stripe_customer_id"],
        unique=True,
    )
    op.add_column(
        "subscriptions",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.create_index(
        op.f("ix_subscriptions_stripe_subscription_id"),
        "subscriptions",
        ["stripe_subscription_id"],
        unique=True,
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_stripe_events_event_type"), "stripe_events", ["event_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_stripe_events_event_type"), table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_index(op.f("ix_subscriptions_stripe_subscription_id"), table_name="subscriptions")
    op.drop_column("subscriptions", "stripe_subscription_id")
    op.drop_index(op.f("ix_tenants_stripe_customer_id"), table_name="tenants")
    op.drop_column("tenants", "stripe_customer_id")
