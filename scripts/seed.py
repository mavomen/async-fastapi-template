#!/usr/bin/env python3
"""Database seeding script for development."""

import asyncio
import os

os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "dev-secret-key-min-32-characters!!!"

from app.core.database import sessionmanager
from app.core.config import settings
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate
from app.models.role import Role, Permission

SEED_USERS = [
    {"email": "admin@example.com", "username": "admin", "password": "Admin123!", "full_name": "Admin User"},
    {"email": "user@example.com", "username": "user", "password": "User1234!", "full_name": "Normal User"},
]

SEED_PERMISSIONS = ["user:read", "user:write", "user:delete"]


async def main():
    sessionmanager.init(settings.DATABASE_URL)

    async with sessionmanager.session() as db:
        # Create permissions
        perms = {}
        for name in SEED_PERMISSIONS:
            perm = Permission(name=name)
            db.add(perm)
            perms[name] = perm
        await db.flush()

        # Create admin role with all permissions
        role = Role(name="admin", description="Administrator")
        role.permissions.extend(perms.values())
        db.add(role)
        await db.flush()

        # Create seed users
        for user_data in SEED_USERS:
            existing = await crud_user.get_by_email(db, email=user_data["email"])
            if not existing:
                user = await crud_user.create(db, obj_in=UserCreate(**user_data))
                # Assign admin role to admin user
                if user_data["username"] == "admin":
                    user.roles.append(role)
                    await db.commit()

        print("Database seeded successfully!")

    await sessionmanager.close()


if __name__ == "__main__":
    asyncio.run(main())
