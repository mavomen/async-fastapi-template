"""Admin dashboard authentication dependencies."""

from fastapi import Depends, HTTPException, status
from app.models.user import User
from app.api.deps import get_current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow only superusers or users with admin role."""
    if not current_user.is_superuser:
        # Check if user has any admin role
        has_admin_role = any(
            role.name == "admin" for role in current_user.roles
        )
        if not has_admin_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
    return current_user
