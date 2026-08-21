"""CMS Page model — static content pages with markdown + HTML dual storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SoftDeleteMixin
from app.models.tenant_base import TenantBaseModel

if TYPE_CHECKING:
    from app.models.category import Category, Tag


class Page(SoftDeleteMixin, TenantBaseModel):
    """A CMS page (e.g. about, terms, privacy policy)."""

    __tablename__ = "cms_pages"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[str | None] = mapped_column(nullable=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    categories: Mapped[list[Category]] = relationship(
        secondary="cms_page_categories",
        back_populates="pages",
    )
    tags: Mapped[list[Tag]] = relationship(
        secondary="cms_page_tags",
        back_populates="pages",
    )

    __table_args__ = (Index("ix_cms_pages_tenant_slug", "tenant_id", "slug", unique=True),)

    def __repr__(self) -> str:
        return f"<Page(id={self.id}, slug={self.slug}, published={self.is_published})>"
