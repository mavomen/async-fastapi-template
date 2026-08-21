"""Tests for Role model."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.identity.models.role import Permission, Role


@pytest.mark.asyncio
async def test_create_role(db_session: AsyncSession):
    role = Role(name="admin", description="Administrator")
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    assert role.id is not None
    assert role.name == "admin"


@pytest.mark.asyncio
async def test_role_with_permissions(db_session: AsyncSession):
    # Create permission first
    perm = Permission(name="edit:articles")
    db_session.add(perm)
    await db_session.flush()

    # Create role and assign permission
    role = Role(name="editor")
    role.permissions.append(perm)
    db_session.add(role)
    await db_session.commit()

    # Reload with eager-loaded permissions to avoid MissingGreenlet
    result = await db_session.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role.id)
    )
    role = result.scalar_one()

    assert len(role.permissions) == 1
    assert role.permissions[0].name == "edit:articles"


@pytest.mark.asyncio
async def test_role_unique_name_constraint(db_session: AsyncSession):
    role1 = Role(name="manager")
    role2 = Role(name="manager")
    db_session.add_all([role1, role2])
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()
