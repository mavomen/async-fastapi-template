"""add files table

Revision ID: 016
Revises: 015
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "016_add_files_table"
down_revision = "015_add_soft_delete"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False, unique=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column(
            "uploader_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("thumbnail_path_small", sa.String(512), nullable=True),
        sa.Column("thumbnail_path_medium", sa.String(512), nullable=True),
        sa.Column("thumbnail_path_large", sa.String(512), nullable=True),
        sa.Column("metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_files_mime_type", "files", ["mime_type"])
    op.create_index("ix_files_checksum_sha256", "files", ["checksum_sha256"])
    op.create_index("ix_files_uploader_id", "files", ["uploader_id"])


def downgrade() -> None:
    op.drop_index("ix_files_uploader_id", table_name="files")
    op.drop_index("ix_files_checksum_sha256", table_name="files")
    op.drop_index("ix_files_mime_type", table_name="files")
    op.drop_table("files")
