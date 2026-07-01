"""Permission-based access control utilities."""

import logging

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_current_user_or_api_key
from app.models.user import User

logger = logging.getLogger(__name__)


def has_permission(user: User, required_permissions: list[str]) -> bool:
    """
    Check if user has all required permissions (via roles), or is superuser.

    Args:
        user: The authenticated user.
        required_permissions: List of permission names required.

    Returns:
        True if user has all permissions, False otherwise.
    """
    if user.is_superuser:
        return True
    if not user.roles:
        logger.debug("User %s has no roles, denying all permissions", user.id)
        return False

    # Collect all permission names from all roles
    user_permissions: set[str] = set()
    for role in user.roles:
        for perm in role.permissions:
            user_permissions.add(perm.name)

    return all(perm in user_permissions for perm in required_permissions)


def check_api_key_scope(api_key_scopes: set[str], required_permissions: list[str]) -> bool:
    return all(p in api_key_scopes for p in required_permissions)


class PermissionChecker:
    """
    FastAPI dependency that checks if the current user has the specified permissions,
    and if the request was authenticated via API key, also checks key scopes.

    Usage:
        @router.get("/users", dependencies=[Depends(PermissionChecker(["user:read"]))])
        Or: current_user: User = Depends(PermissionChecker(["user:write"]))
    """

    def __init__(self, required_permissions: list[str]):
        self.required_permissions = required_permissions

    def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user_or_api_key),
    ) -> User:
        if not has_permission(current_user, self.required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        api_key_scopes: set[str] | None = getattr(request.state, "api_key_scopes", None)
        if api_key_scopes is not None and not check_api_key_scope(api_key_scopes, self.required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key does not have the required scopes",
            )
        return current_user
