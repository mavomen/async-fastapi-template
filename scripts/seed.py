#!/usr/bin/env python3
"""Database seeding script for development."""

import asyncio
import os

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "dev-secret-key-min-32-characters!!!"

from sqlalchemy import select

from app.core.config import settings
from app.core.database import sessionmanager
from app.crud.user import user as crud_user
from app.models.role import Permission, Role
from app.schemas.user import UserCreate

SEED_USERS = [
    {
        "email": "admin@example.com",
        "username": "admin",
        "password": "Admin123!",
        "full_name": "Admin User",
    },
    {
        "email": "user@example.com",
        "username": "user",
        "password": "User1234!",
        "full_name": "Normal User",
    },
]

SEED_PERMISSIONS = [
    "user:read",
    "user:write",
    "user:delete",
    "webhook:read",
    "webhook:write",
]


async def get_or_create_permission(db, name: str) -> Permission:
    result = await db.execute(select(Permission).where(Permission.name == name))
    perm = result.scalar_one_or_none()
    if perm is None:
        perm = Permission(name=name)
        db.add(perm)
        await db.flush()
    return perm


async def get_or_create_role(db, name: str, description: str) -> Role:
    result = await db.execute(select(Role).where(Role.name == name))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name=name, description=description)
        db.add(role)
        await db.flush()
    return role


async def main():
    sessionmanager.init(settings.DATABASE_URL)

    async with sessionmanager.session() as db:
        # Create or fetch permissions
        perms = {}
        for name in SEED_PERMISSIONS:
            perms[name] = await get_or_create_permission(db, name)

        # Create or fetch admin role
        role = await get_or_create_role(db, "admin", "Administrator")
        role.permissions.extend(p for p in perms.values() if p not in role.permissions)
        await db.flush()

        # Create seed users
        for user_data in SEED_USERS:
            existing = await crud_user.get_by_email(db, email=user_data["email"])
            if not existing:
                user = await crud_user.create(db, obj_in=UserCreate(**user_data))
                if user_data["username"] == "admin":
                    user.roles.append(role)
                    await db.commit()

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
