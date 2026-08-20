"""Pydantic schemas for CMS content (Pages, Posts, Categories, Tags)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------- Category ----------


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(None, max_length=500)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int | None = None


# ---------- Tag ----------


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    slug: str | None = Field(None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class TagRead(TagBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int | None = None


# ---------- Page ----------


class PageBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    body_md: str | None = None
    meta_title: str | None = Field(None, max_length=255)
    meta_description: str | None = Field(None, max_length=500)
    is_published: bool = False


class PageCreate(PageBase):
    category_ids: list[int] = []
    tag_ids: list[int] = []


class PageUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    body_md: str | None = None
    meta_title: str | None = Field(None, max_length=255)
    meta_description: str | None = Field(None, max_length=500)
    is_published: bool | None = None
    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None


class PageRead(PageBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    body_html: str | None = None
    author_id: int | None = None
    published_at: str | None = None
    tenant_id: int | None = None
    created_at: datetime
    updated_at: datetime
    categories: list[CategoryRead] = []
    tags: list[TagRead] = []


# ---------- Post ----------


class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    excerpt: str | None = Field(None, max_length=500)
    body_md: str | None = None
    cover_image_url: str | None = Field(None, max_length=500)
    meta_title: str | None = Field(None, max_length=255)
    meta_description: str | None = Field(None, max_length=500)
    is_published: bool = False


class PostCreate(PostBase):
    category_ids: list[int] = []
    tag_ids: list[int] = []


class PostUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    excerpt: str | None = Field(None, max_length=500)
    body_md: str | None = None
    cover_image_url: str | None = Field(None, max_length=500)
    meta_title: str | None = Field(None, max_length=255)
    meta_description: str | None = Field(None, max_length=500)
    is_published: bool | None = None
    category_ids: list[int] | None = None
    tag_ids: list[int] | None = None


class PostRead(PostBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    body_html: str | None = None
    author_id: int | None = None
    published_at: str | None = None
    tenant_id: int | None = None
    created_at: datetime
    updated_at: datetime
    categories: list[CategoryRead] = []
    tags: list[TagRead] = []


class PageListResponse(BaseModel):
    items: list[PageRead]
    total: int


class PostListResponse(BaseModel):
    items: list[PostRead]
    total: int
