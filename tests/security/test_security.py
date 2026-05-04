"""Tests for XSS sanitisation utility."""

from app.utils.xss import sanitize_input


def test_xss_sanitization():
    """HTML characters are escaped."""
    dangerous = '<script>alert("XSS")</script>'
    safe = sanitize_input(dangerous)
    assert "&lt;" in safe  # < replaced with &lt;
    assert "<" not in safe  # no raw HTML tags remain
