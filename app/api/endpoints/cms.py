"""API endpoints for CMS content (Pages, Posts, Categories, Tags)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_read_db
from app.crud import cms as crud_cms
from app.models.user import User
from app.schemas.cms import (
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    PageCreate,
    PageListResponse,
    PageRead,
    PageUpdate,
    PostCreate,
    PostListResponse,
    PostRead,
    PostUpdate,
    TagCreate,
    TagRead,
)

router = APIRouter()


# ---------- Pages ----------


@router.get("/pages", response_model=PageListResponse)
async def list_pages(
    db: AsyncSession = Depends(get_read_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PageListResponse:
    items = await crud_cms.page.get_multi_with_relations(db, skip=skip, limit=limit)
    total = await crud_cms.page.count(db)
    return PageListResponse(items=items, total=total)


@router.get("/pages/{slug}", response_model=PageRead)
async def get_page(slug: str, db: AsyncSession = Depends(get_read_db)) -> Any:
    page = await crud_cms.page.get_by_slug(db, slug=slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.post("/pages", response_model=PageRead, status_code=201)
async def create_page(
    page_in: PageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    existing = await crud_cms.page.get_by_slug(db, slug=page_in.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Page with this slug already exists")
    page = await crud_cms.page.create_with_relations(
        db, obj_in=page_in, tenant_id=current_user.tenant_id, author_id=current_user.id
    )
    return page


@router.put("/pages/{slug}", response_model=PageRead)
async def update_page(
    slug: str,
    page_in: PageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    page = await crud_cms.page.get_by_slug(db, slug=slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    if page_in.slug and page_in.slug != slug:
        existing = await crud_cms.page.get_by_slug(db, slug=page_in.slug)
        if existing:
            raise HTTPException(status_code=409, detail="Page with this slug already exists")
    page = await crud_cms.page.update_with_relations(db, db_obj=page, obj_in=page_in)
    return page


@router.delete("/pages/{slug}", status_code=204)
async def delete_page(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    page = await crud_cms.page.get_by_slug(db, slug=slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    await crud_cms.page.delete(db, id=page.id)


# ---------- Posts ----------


@router.get("/posts", response_model=PostListResponse)
async def list_posts(
    db: AsyncSession = Depends(get_read_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    published_only: bool = Query(False),
) -> PostListResponse:
    items = await crud_cms.post.get_multi_with_relations(
        db, skip=skip, limit=limit, published_only=published_only
    )
    total = await crud_cms.post.count(db)
    return PostListResponse(items=items, total=total)


@router.get("/posts/{slug}", response_model=PostRead)
async def get_post(slug: str, db: AsyncSession = Depends(get_read_db)) -> Any:
    post = await crud_cms.post.get_by_slug(db, slug=slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/posts", response_model=PostRead, status_code=201)
async def create_post(
    post_in: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    existing = await crud_cms.post.get_by_slug(db, slug=post_in.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Post with this slug already exists")
    post = await crud_cms.post.create_with_relations(
        db, obj_in=post_in, tenant_id=current_user.tenant_id, author_id=current_user.id
    )
    return post


@router.put("/posts/{slug}", response_model=PostRead)
async def update_post(
    slug: str,
    post_in: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    post = await crud_cms.post.get_by_slug(db, slug=slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post_in.slug and post_in.slug != slug:
        existing = await crud_cms.post.get_by_slug(db, slug=post_in.slug)
        if existing:
            raise HTTPException(status_code=409, detail="Post with this slug already exists")
    post = await crud_cms.post.update_with_relations(db, db_obj=post, obj_in=post_in)
    return post


@router.delete("/posts/{slug}", status_code=204)
async def delete_post(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    post = await crud_cms.post.get_by_slug(db, slug=slug)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await crud_cms.post.delete(db, id=post.id)


# ---------- Categories ----------


@router.get("/categories", response_model=list[CategoryRead])
async def list_categories(db: AsyncSession = Depends(get_read_db)) -> Any:
    items = await crud_cms.category.get_multi(db, limit=100)
    return items


@router.post("/categories", response_model=CategoryRead, status_code=201)
async def create_category(
    cat_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    existing = await crud_cms.category.get_by_slug(db, slug=cat_in.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Category with this slug already exists")
    return await crud_cms.category.create(db, obj_in=cat_in)


@router.put("/categories/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int,
    cat_in: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    cat = await crud_cms.category.get(db, id=category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return await crud_cms.category.update(db, db_obj=cat, obj_in=cat_in)


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    cat = await crud_cms.category.get(db, id=category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    await crud_cms.category.delete(db, id=category_id)


# ---------- Tags ----------


@router.get("/tags", response_model=list[TagRead])
async def list_tags(db: AsyncSession = Depends(get_read_db)) -> Any:
    items = await crud_cms.tag.get_multi(db, limit=100)
    return items


@router.post("/tags", response_model=TagRead, status_code=201)
async def create_tag(
    tag_in: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    existing = await crud_cms.tag.get_by_slug(db, slug=tag_in.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Tag with this slug already exists")
    return await crud_cms.tag.create(db, obj_in=tag_in)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    t = await crud_cms.tag.get(db, id=tag_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tag not found")
    await crud_cms.tag.delete(db, id=tag_id)
