"""Markdown rendering service — mistune v3 + bleach sanitization."""

from __future__ import annotations

import re

import bleach
import mistune

_ALLOWED_TAGS = list(bleach.ALLOWED_TAGS) + [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "pre",
    "code",
    "img",
    "figure",
    "figcaption",
    "del",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "dl",
    "dt",
    "dd",
    "details",
    "summary",
]

_ALLOWED_ATTRIBUTES = {
    **bleach.ALLOWED_ATTRIBUTES,
    "img": ["src", "alt", "title", "width", "height"],
    "a": ["href", "title", "rel"],
    "code": ["class"],
    "pre": ["class"],
}

_SCRIPT_STYLE_RE = re.compile(
    r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)

_markdown = mistune.create_markdown(
    escape=False,
    plugins=["strikethrough", "table"],
)


def render_markdown(text: str | None) -> str | None:
    """Render markdown to sanitized HTML.

    Args:
        text: Markdown source text.

    Returns:
        Sanitized HTML string, or None if input is None.
    """
    if not text:
        return None
    html = _markdown(text)
    if not isinstance(html, str):
        return None
    html = _SCRIPT_STYLE_RE.sub("", html)
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRIBUTES, strip=True)
