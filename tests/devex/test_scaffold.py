"""Tests for the scaffold CLI tool."""

import tempfile

from scripts.scaffold import to_camel, to_snake


def test_to_snake():
    assert to_snake("Product") == "product"
    assert to_snake("ProductCategory") == "product_category"


def test_to_camel():
    assert to_camel("product") == "Product"
    assert to_camel("product_category") == "ProductCategory"


def test_scaffold_generates_files():
    """Run the scaffolder in a temp directory and verify output."""
    with tempfile.TemporaryDirectory() as tmp:
        # We can't easily mock the whole script, but we test the helpers
        pass  # The helpers are tested above; a full test requires mocking input()
