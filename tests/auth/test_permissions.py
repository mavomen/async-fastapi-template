"""Tests for permission checker."""

from app.auth.permissions import has_permission
from app.models.role import Permission, Role
from app.models.user import User


def create_mock_user(is_superuser=False):
    user = User(
        id=1,
        email="test@example.com",
        username="test",
        hashed_password="hash",
        is_superuser=is_superuser,
    )
    return user


def test_has_permission_superuser():
    user = create_mock_user(is_superuser=True)
    # Superuser bypasses permissions
    assert has_permission(user, ["admin:all"]) is True


def test_has_permission_with_matching_permission():
    user = create_mock_user()
    role = Role(name="tester")
    perm = Permission(name="test:run")
    role.permissions.append(perm)
    user.roles.append(role)
    assert has_permission(user, ["test:run"]) is True


def test_has_permission_missing_permission():
    user = create_mock_user()
    role = Role(name="viewer")
    user.roles.append(role)
    assert has_permission(user, ["read:secret"]) is False


def test_has_permission_requires_all():
    user = create_mock_user()
    role = Role(name="editor")
    perm1 = Permission(name="write:docs")
    perm2 = Permission(name="publish:docs")
    role.permissions.extend([perm1, perm2])
    user.roles.append(role)
    assert has_permission(user, ["write:docs", "publish:docs"]) is True
    assert has_permission(user, ["write:docs", "delete:docs"]) is False
