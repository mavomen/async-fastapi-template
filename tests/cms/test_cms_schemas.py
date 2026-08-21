"""Extended schema validation tests for CMS content."""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.cms import CategoryCreate, PageCreate, PostCreate

_SLUG_RE = re.compile(r"[a-z0-9-]+")


class TestPageSlugHypothesis:
    @given(slug=st.from_regex(r"[a-z0-9-]{1,255}", fullmatch=True))
    @settings(max_examples=100)
    def test_valid_slugs_accepted(self, slug: str) -> None:
        page = PageCreate(title="Test", slug=slug)
        assert page.slug == slug

    @given(slug=st.text(min_size=1, max_size=255).filter(lambda s: _SLUG_RE.fullmatch(s) is None))
    @settings(max_examples=50)
    def test_invalid_slugs_rejected(self, slug: str) -> None:
        with pytest.raises(ValidationError):
            PageCreate(title="Test", slug=slug)


class TestPostSlugHypothesis:
    @given(slug=st.from_regex(r"[a-z0-9-]{1,255}", fullmatch=True))
    @settings(max_examples=100)
    def test_valid_slugs_accepted(self, slug: str) -> None:
        post = PostCreate(title="Test", slug=slug)
        assert post.slug == slug


class TestCategorySlugHypothesis:
    @given(slug=st.from_regex(r"[a-z0-9-]{1,100}", fullmatch=True))
    @settings(max_examples=100)
    def test_valid_slugs_accepted(self, slug: str) -> None:
        cat = CategoryCreate(name="Test", slug=slug)
        assert cat.slug == slug
