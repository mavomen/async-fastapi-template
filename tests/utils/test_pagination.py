"""Tests for pagination utilities."""

import pytest
from pydantic import ValidationError

from app.utils.pagination import Page, Params


class TestParams:
    """Test Params class."""

    def test_default_params(self):
        """Test default pagination parameters."""
        params = Params()

        assert params.page == 1
        assert params.size == 50

    def test_custom_params(self):
        """Test custom pagination parameters."""
        params = Params(page=2, size=25)

        assert params.page == 2
        assert params.size == 25

    def test_skip_calculation(self):
        """Test skip calculation."""
        params1 = Params(page=1, size=10)
        assert params1.skip == 0

        params2 = Params(page=2, size=10)
        assert params2.skip == 10

        params3 = Params(page=5, size=20)
        assert params3.skip == 80

    def test_limit_property(self):
        """Test limit property returns size."""
        params = Params(page=1, size=30)
        assert params.limit == 30

    def test_page_minimum_value(self):
        """Test page must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            Params(page=0)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("page",) for error in errors)

    def test_page_negative_value(self):
        """Test page cannot be negative."""
        with pytest.raises(ValidationError) as exc_info:
            Params(page=-1)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("page",) for error in errors)

    def test_size_minimum_value(self):
        """Test size must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            Params(size=0)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("size",) for error in errors)

    def test_size_maximum_value(self):
        """Test size cannot exceed 100."""
        with pytest.raises(ValidationError) as exc_info:
            Params(size=101)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("size",) for error in errors)

    def test_size_at_maximum(self):
        """Test size can be exactly 100."""
        params = Params(size=100)
        assert params.size == 100


class TestPage:
    """Test Page class."""

    def test_create_page_first_page(self):
        """Test creating first page."""
        items = [1, 2, 3, 4, 5]
        params = Params(page=1, size=5)
        total = 20

        page = Page.create(items=items, total=total, params=params)

        assert page.items == items
        assert page.total == 20
        assert page.page == 1
        assert page.size == 5
        assert page.pages == 4

    def test_create_page_middle_page(self):
        """Test creating middle page."""
        items = [6, 7, 8, 9, 10]
        params = Params(page=2, size=5)
        total = 20

        page = Page.create(items=items, total=total, params=params)

        assert page.items == items
        assert page.page == 2
        assert page.pages == 4

    def test_create_page_last_page(self):
        """Test creating last page with partial items."""
        items = [16, 17, 18, 19, 20]
        params = Params(page=4, size=5)
        total = 20

        page = Page.create(items=items, total=total, params=params)

        assert page.items == items
        assert page.page == 4
        assert page.pages == 4

    def test_create_page_empty_results(self):
        """Test creating page with no results."""
        items = []
        params = Params(page=1, size=10)
        total = 0

        page = Page.create(items=items, total=total, params=params)

        assert page.items == []
        assert page.total == 0
        assert page.pages == 0

    def test_create_page_single_page(self):
        """Test creating page when all items fit in one page."""
        items = [1, 2, 3]
        params = Params(page=1, size=10)
        total = 3

        page = Page.create(items=items, total=total, params=params)

        assert page.items == items
        assert page.total == 3
        assert page.pages == 1

    def test_create_page_partial_last_page(self):
        """Test pages calculation with partial last page."""
        items = [21, 22]
        params = Params(page=3, size=10)
        total = 22

        page = Page.create(items=items, total=total, params=params)

        assert page.pages == 3  # 10 + 10 + 2

    def test_create_page_exact_multiple(self):
        """Test pages calculation when total is exact multiple of size."""
        items = [21, 22, 23, 24, 25]
        params = Params(page=5, size=5)
        total = 25

        page = Page.create(items=items, total=total, params=params)

        assert page.pages == 5  # Exactly 5 pages

    def test_page_with_different_types(self):
        """Test Page works with different item types."""
        # Test with strings
        string_items = ["a", "b", "c"]
        params = Params(page=1, size=10)
        string_page = Page.create(items=string_items, total=3, params=params)
        assert string_page.items == string_items

        # Test with dicts
        dict_items = [{"id": 1}, {"id": 2}]
        dict_page = Page.create(items=dict_items, total=2, params=params)
        assert dict_page.items == dict_items
