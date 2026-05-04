"""Utility to sanitise input strings against XSS."""

import html


def sanitize_input(value: str) -> str:
    """Escape HTML characters to prevent XSS."""
    return html.escape(value, quote=True)
