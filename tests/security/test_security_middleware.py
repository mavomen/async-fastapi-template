"""Tests for security headers, SQL injection logging, and XSS utility."""

from fastapi.testclient import TestClient


def test_security_headers_present(client: TestClient):
    """Responses must include required security headers."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "0"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src" in response.headers["Content-Security-Policy"]


def test_sql_injection_logging(caplog):
    """Suspicious patterns are logged but request passes."""
    from app.main import app as _app

    client = TestClient(_app)
    response = client.get("/health?q=1' OR '1'='1")
    assert response.status_code == 200
    log_messages = [r.message for r in caplog.records]
    assert any("Potential SQL injection" in msg for msg in log_messages)


def test_xss_sanitization():
    """HTML characters are escaped."""
    from app.utils.xss import sanitize_input

    dangerous = '<script>alert("XSS")</script>'
    safe = sanitize_input(dangerous)
    assert "&lt;script&gt;" in safe
    assert "<script>" not in safe
