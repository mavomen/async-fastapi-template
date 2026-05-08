"""Unit tests for admin helper _coerce_value."""

from app.admin import _coerce_value
from app.models.user import User


def test_coerce_boolean_true():
    assert _coerce_value(User, "is_active", "1") is True
    assert _coerce_value(User, "is_active", "true") is True
    assert _coerce_value(User, "is_active", "on") is True


def test_coerce_boolean_false():
    assert _coerce_value(User, "is_active", "0") is False
    assert _coerce_value(User, "is_active", "false") is False


def test_coerce_unknown_column():
    assert _coerce_value(User, "nonexistent", "anything") == "anything"


def test_coerce_string():
    assert _coerce_value(User, "email", "test@test.com") == "test@test.com"
