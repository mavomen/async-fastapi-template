"""add cms tables

Revision ID: 017_cms
Revises: 016_add_files_table
Create Date: 2026-08-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017_cms"
down_revision: str | None = "016_add_files_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cms_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cms_categories_tenant_slug", "cms_categories", ["tenant_id", "slug"], unique=True
    )

    op.create_table(
        "cms_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cms_tags_tenant_slug", "cms_tags", ["tenant_id", "slug"], unique=True)

    op.create_table(
        "cms_pages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("meta_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("is_published", sa.Boolean(), default=False, nullable=False),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cms_pages_tenant_slug", "cms_pages", ["tenant_id", "slug"], unique=True)

    op.create_table(
        "cms_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("excerpt", sa.String(500), nullable=True),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("cover_image_url", sa.String(500), nullable=True),
        sa.Column("meta_title", sa.String(255), nullable=True),
        sa.Column("meta_description", sa.String(500), nullable=True),
        sa.Column("is_published", sa.Boolean(), default=False, nullable=False),
        sa.Column("published_at", sa.String(), nullable=True),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cms_posts_tenant_slug", "cms_posts", ["tenant_id", "slug"], unique=True)

    op.create_table(
        "cms_page_categories",
        sa.Column(
            "page_id",
            sa.Integer(),
            sa.ForeignKey("cms_pages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("cms_categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "cms_post_categories",
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("cms_posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("cms_categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "cms_page_tags",
        sa.Column(
            "page_id",
            sa.Integer(),
            sa.ForeignKey("cms_pages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("cms_tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "cms_post_tags",
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("cms_posts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("cms_tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("cms_post_tags")
    op.drop_table("cms_page_tags")
    op.drop_table("cms_post_categories")
    op.drop_table("cms_page_categories")
    op.drop_index("ix_cms_posts_tenant_slug", table_name="cms_posts")
    op.drop_table("cms_posts")
    op.drop_index("ix_cms_pages_tenant_slug", table_name="cms_pages")
    op.drop_table("cms_pages")
    op.drop_index("ix_cms_tags_tenant_slug", table_name="cms_tags")
    op.drop_table("cms_tags")
    op.drop_index("ix_cms_categories_tenant_slug", table_name="cms_categories")
    op.drop_table("cms_categories")
