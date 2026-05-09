"""Unit test for SearchMixin."""

from app.models.search import SearchMixin


def test_search_query_returns_expression():
    expr = SearchMixin.search_query("hello")
    assert expr is not None
    # The expression contains websearch_to_tsquery
    assert "websearch_to_tsquery" in str(expr)
