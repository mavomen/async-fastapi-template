"""CMS Category and Tag models for content classification."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.tenant_base import TenantBaseModel

# Association tables
cms_page_categories = Table(
    "cms_page_categories",
    BaseModel.metadata,
    Column("page_id", Integer, ForeignKey("cms_pages.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id",
        Integer,
        ForeignKey("cms_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

cms_post_categories = Table(
    "cms_post_categories",
    BaseModel.metadata,
    Column("post_id", Integer, ForeignKey("cms_posts.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "category_id",
        Integer,
        ForeignKey("cms_categories.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

cms_page_tags = Table(
    "cms_page_tags",
    BaseModel.metadata,
    Column("page_id", Integer, ForeignKey("cms_pages.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("cms_tags.id", ondelete="CASCADE"), primary_key=True),
)

cms_post_tags = Table(
    "cms_post_tags",
    BaseModel.metadata,
    Column("post_id", Integer, ForeignKey("cms_posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("cms_tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(TenantBaseModel):
    """A CMS category for grouping content."""

    __tablename__ = "cms_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    pages: Mapped[list[Page]] = relationship(  # type: ignore[name-defined]
        secondary=cms_page_categories,
        back_populates="categories",
    )
    posts: Mapped[list[Post]] = relationship(  # type: ignore[name-defined]
        secondary=cms_post_categories,
        back_populates="categories",
    )

    __table_args__ = (Index("ix_cms_categories_tenant_slug", "tenant_id", "slug", unique=True),)

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name})>"


class Tag(TenantBaseModel):
    """A CMS tag for labeling content."""

    __tablename__ = "cms_tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)

    pages: Mapped[list[Page]] = relationship(  # type: ignore[name-defined]
        secondary=cms_page_tags,
        back_populates="tags",
    )
    posts: Mapped[list[Post]] = relationship(  # type: ignore[name-defined]
        secondary=cms_post_tags,
        back_populates="tags",
    )

    __table_args__ = (Index("ix_cms_tags_tenant_slug", "tenant_id", "slug", unique=True),)

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name})>"
