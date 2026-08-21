"""CRUD operations for CMS content (Pages, Posts, Categories, Tags)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.category import Category, Tag
from app.models.page import Page
from app.models.post import Post
from app.schemas.cms import (
    CategoryCreate,
    CategoryUpdate,
    PageCreate,
    PageUpdate,
    PostCreate,
    PostUpdate,
    TagCreate,
    TagUpdate,
)


class CRUDPage(CRUDBase[Page, PageCreate, PageUpdate]):
    async def create_with_relations(
        self,
        db: AsyncSession,
        *,
        obj_in: PageCreate,
        tenant_id: int | None = None,
        author_id: int | None = None,
    ) -> Page:
        from app.services.markdown_service import render_markdown

        db_obj = Page(
            title=obj_in.title,
            slug=obj_in.slug,
            body_md=obj_in.body_md,
            body_html=render_markdown(obj_in.body_md),
            meta_title=obj_in.meta_title,
            meta_description=obj_in.meta_description,
            is_published=obj_in.is_published,
            tenant_id=tenant_id,
            author_id=author_id,
        )
        db.add(db_obj)
        await db.flush()
        if obj_in.category_ids:
            cats = (
                (await db.execute(select(Category).where(Category.id.in_(obj_in.category_ids))))
                .scalars()
                .all()
            )
            db_obj.categories = list(cats)
        if obj_in.tag_ids:
            tags = (await db.execute(select(Tag).where(Tag.id.in_(obj_in.tag_ids)))).scalars().all()
            db_obj.tags = list(tags)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_with_relations(
        self, db: AsyncSession, *, db_obj: Page, obj_in: PageUpdate
    ) -> Page:
        from app.services.markdown_service import render_markdown

        update_data = obj_in.model_dump(exclude_unset=True)
        category_ids = update_data.pop("category_ids", None)
        tag_ids = update_data.pop("tag_ids", None)
        if "body_md" in update_data:
            update_data["body_html"] = render_markdown(update_data["body_md"])
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        if category_ids is not None:
            cats = (
                (await db.execute(select(Category).where(Category.id.in_(category_ids))))
                .scalars()
                .all()
            )
            db_obj.categories = list(cats)
        if tag_ids is not None:
            tags = (await db.execute(select(Tag).where(Tag.id.in_(tag_ids)))).scalars().all()
            db_obj.tags = list(tags)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_slug(
        self, db: AsyncSession, *, slug: str, tenant_id: int | None = None
    ) -> Page | None:
        stmt = select(Page).where(Page.slug == slug, Page.deleted_at.is_(None))
        if tenant_id is not None:
            stmt = stmt.where(Page.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_relations(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
        tenant_id: int | None = None,
        published_only: bool = False,
    ) -> list[Page]:
        stmt = (
            select(Page)
            .options(selectinload(Page.categories), selectinload(Page.tags))
            .where(Page.deleted_at.is_(None))
            .order_by(Page.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(Page.tenant_id == tenant_id)
        if published_only:
            stmt = stmt.where(Page.is_published.is_(True))
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(  # type: ignore[override]
        self, db: AsyncSession, *, tenant_id: int | None = None
    ) -> int:
        stmt = select(func.count()).select_from(Page).where(Page.deleted_at.is_(None))
        if tenant_id is not None:
            stmt = stmt.where(Page.tenant_id == tenant_id)
        return (await db.scalar(stmt)) or 0


class CRUDPost(CRUDBase[Post, PostCreate, PostUpdate]):
    async def create_with_relations(
        self,
        db: AsyncSession,
        *,
        obj_in: PostCreate,
        tenant_id: int | None = None,
        author_id: int | None = None,
    ) -> Post:
        from app.services.markdown_service import render_markdown

        db_obj = Post(
            title=obj_in.title,
            slug=obj_in.slug,
            excerpt=obj_in.excerpt,
            body_md=obj_in.body_md,
            body_html=render_markdown(obj_in.body_md),
            cover_image_url=obj_in.cover_image_url,
            meta_title=obj_in.meta_title,
            meta_description=obj_in.meta_description,
            is_published=obj_in.is_published,
            tenant_id=tenant_id,
            author_id=author_id,
        )
        db.add(db_obj)
        await db.flush()
        if obj_in.category_ids:
            cats = (
                (await db.execute(select(Category).where(Category.id.in_(obj_in.category_ids))))
                .scalars()
                .all()
            )
            db_obj.categories = list(cats)
        if obj_in.tag_ids:
            tags = (await db.execute(select(Tag).where(Tag.id.in_(obj_in.tag_ids)))).scalars().all()
            db_obj.tags = list(tags)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_with_relations(
        self, db: AsyncSession, *, db_obj: Post, obj_in: PostUpdate
    ) -> Post:
        from app.services.markdown_service import render_markdown

        update_data = obj_in.model_dump(exclude_unset=True)
        category_ids = update_data.pop("category_ids", None)
        tag_ids = update_data.pop("tag_ids", None)
        if "body_md" in update_data:
            update_data["body_html"] = render_markdown(update_data["body_md"])
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        if category_ids is not None:
            cats = (
                (await db.execute(select(Category).where(Category.id.in_(category_ids))))
                .scalars()
                .all()
            )
            db_obj.categories = list(cats)
        if tag_ids is not None:
            tags = (await db.execute(select(Tag).where(Tag.id.in_(tag_ids)))).scalars().all()
            db_obj.tags = list(tags)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_slug(
        self, db: AsyncSession, *, slug: str, tenant_id: int | None = None
    ) -> Post | None:
        stmt = select(Post).where(Post.slug == slug, Post.deleted_at.is_(None))
        if tenant_id is not None:
            stmt = stmt.where(Post.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_relations(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
        tenant_id: int | None = None,
        published_only: bool = False,
    ) -> list[Post]:
        stmt = (
            select(Post)
            .options(selectinload(Post.categories), selectinload(Post.tags))
            .where(Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(Post.tenant_id == tenant_id)
        if published_only:
            stmt = stmt.where(Post.is_published.is_(True))
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count(  # type: ignore[override]
        self, db: AsyncSession, *, tenant_id: int | None = None
    ) -> int:
        stmt = select(func.count()).select_from(Post).where(Post.deleted_at.is_(None))
        if tenant_id is not None:
            stmt = stmt.where(Post.tenant_id == tenant_id)
        return (await db.scalar(stmt)) or 0


class CRUDCategory(CRUDBase[Category, CategoryCreate, CategoryUpdate]):
    async def get_by_slug(
        self, db: AsyncSession, *, slug: str, tenant_id: int | None = None
    ) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        if tenant_id is not None:
            stmt = stmt.where(Category.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


class CRUDTag(CRUDBase[Tag, TagCreate, TagUpdate]):
    async def get_by_slug(
        self, db: AsyncSession, *, slug: str, tenant_id: int | None = None
    ) -> Tag | None:
        stmt = select(Tag).where(Tag.slug == slug)
        if tenant_id is not None:
            stmt = stmt.where(Tag.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


page = CRUDPage(Page)
post = CRUDPost(Post)
category = CRUDCategory(Category)
tag = CRUDTag(Tag)
