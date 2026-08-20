"""Tests for the markdown rendering service."""

from __future__ import annotations

from app.services.markdown_service import render_markdown


class TestRenderMarkdown:
    def test_none_returns_none(self) -> None:
        assert render_markdown(None) is None

    def test_empty_returns_none(self) -> None:
        assert render_markdown("") is None

    def test_basic_heading(self) -> None:
        html = render_markdown("# Hello")
        assert "<h1>Hello</h1>" in html

    def test_paragraph(self) -> None:
        html = render_markdown("Some text here.")
        assert "<p>Some text here.</p>" in html

    def test_bold(self) -> None:
        html = render_markdown("**bold text**")
        assert "<strong>bold text</strong>" in html

    def test_italic(self) -> None:
        html = render_markdown("*italic text*")
        assert "<em>italic text</em>" in html

    def test_code_block(self) -> None:
        md = "```python\nprint('hello')\n```"
        html = render_markdown(md)
        assert "<code" in html or "<pre" in html

    def test_link(self) -> None:
        html = render_markdown("[click here](https://example.com)")
        assert 'href="https://example.com"' in html

    def test_image(self) -> None:
        html = render_markdown("![alt](https://example.com/img.png)")
        assert "<img" in html
        assert "alt" in html

    def test_strikethrough(self) -> None:
        html = render_markdown("~~deleted~~")
        assert "<del>deleted</del>" in html

    def test_script_tag_stripped(self) -> None:
        html = render_markdown("<script>alert('xss')</script>")
        assert "<script>" not in html
        assert "alert" not in html

    def test_onerror_stripped(self) -> None:
        html = render_markdown('<img src="x" onerror="alert(1)">')
        assert "onerror" not in html

    def test_table(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = render_markdown(md)
        assert "<table" in html

    def test_list(self) -> None:
        md = "- item 1\n- item 2"
        html = render_markdown(md)
        assert "<ul" in html
        assert "<li" in html
