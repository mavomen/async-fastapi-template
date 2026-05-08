"""Unit tests for admin helper functions."""

from app.admin import _coerce_value, _set_default_password_for_user, register_admin
from app.models.user import User


def test_register_admin_stores_model():
    """Verify register_admin() adds a model to the registry."""
    register_admin(User, list_display=["email"], permission="custom:admin")
    from app.admin import _registry

    assert "users" in _registry
    assert _registry["users"]["model"] is User
    assert _registry["users"]["permission"] == "custom:admin"


def test_coerce_boolean():
    """_coerce_value() should convert string '1'/'true' to Python boolean."""
    assert _coerce_value(User, "is_active", "1") is True
    assert _coerce_value(User, "is_active", "true") is True
    assert _coerce_value(User, "is_active", "0") is False
    assert _coerce_value(User, "is_active", "false") is False


def test_set_default_password_for_user_assigns_placeholder():
    """_set_default_password_for_user() should assign a hashed password if none exists."""
    user = User(email="test@test.com", username="test")
    assert not user.hashed_password
    _set_default_password_for_user(user)
    assert user.hashed_password
    assert len(user.hashed_password) > 20


def test_register_role_model():
    """register_admin() works for Role model."""
    from app.models.role import Role

    register_admin(Role, list_display=["name"], permission="role:admin")
    from app.admin import _registry

    assert "roles" in _registry
    assert _registry["roles"]["model"] is Role
