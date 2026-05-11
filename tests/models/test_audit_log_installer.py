"""Test that install_audit_log_listener is importable and callable."""

from app.models.audit_log import install_audit_log_listener


def test_install_audit_log_listener_exists():
    assert callable(install_audit_log_listener)
