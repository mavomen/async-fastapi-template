"""Tests for CMS models and schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.cms import (
    CategoryCreate,
    CategoryUpdate,
    PageCreate,
    PageUpdate,
    PostCreate,
    PostUpdate,
    TagCreate,
)


class TestCategorySchema:
    def test_create_valid(self) -> None:
        cat = CategoryCreate(name="Tech", slug="tech", description="Technology articles")
        assert cat.name == "Tech"
        assert cat.slug == "tech"

    def test_create_slug_validation(self) -> None:
        with pytest.raises(ValidationError):
            CategoryCreate(name="Tech", slug="Tech With Spaces")

    def test_update_partial(self) -> None:
        update = CategoryUpdate(name="Updated")
        data = update.model_dump(exclude_unset=True)
        assert "name" in data
        assert "slug" not in data


class TestTagSchema:
    def test_create_valid(self) -> None:
        tag = TagCreate(name="Python", slug="python")
        assert tag.name == "Python"

    def test_create_slug_validation(self) -> None:
        with pytest.raises(ValidationError):
            TagCreate(name="Python", slug="INVALID SLUG!")


class TestPageSchema:
    def test_create_valid(self) -> None:
        page = PageCreate(title="About", slug="about", body_md="# About Us")
        assert page.title == "About"
        assert page.is_published is False

    def test_create_with_relations(self) -> None:
        page = PageCreate(
            title="Terms",
            slug="terms",
            body_md="Terms content",
            category_ids=[1, 2],
            tag_ids=[3],
        )
        assert page.category_ids == [1, 2]
        assert page.tag_ids == [3]

    def test_title_required(self) -> None:
        with pytest.raises(ValidationError):
            PageCreate(slug="about")

    def test_slug_validation(self) -> None:
        with pytest.raises(ValidationError):
            PageCreate(title="About", slug="About Page!")


class TestPostSchema:
    def test_create_valid(self) -> None:
        post = PostCreate(
            title="Hello World",
            slug="hello-world",
            body_md="# Hello",
            excerpt="My first post",
        )
        assert post.title == "Hello World"
        assert post.excerpt == "My first post"

    def test_create_with_relations(self) -> None:
        post = PostCreate(
            title="Test",
            slug="test",
            category_ids=[1],
            tag_ids=[2, 3],
        )
        assert post.category_ids == [1]
        assert post.tag_ids == [2, 3]


class TestPageUpdate:
    def test_partial_update(self) -> None:
        update = PageUpdate(title="New Title")
        data = update.model_dump(exclude_unset=True)
        assert "title" in data
        assert "slug" not in data

    def test_is_published_toggle(self) -> None:
        update = PageUpdate(is_published=True)
        data = update.model_dump(exclude_unset=True)
        assert data["is_published"] is True


class TestPostUpdate:
    def test_partial_update(self) -> None:
        update = PostUpdate(excerpt="Updated excerpt")
        data = update.model_dump(exclude_unset=True)
        assert data["excerpt"] == "Updated excerpt"
