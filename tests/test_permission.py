"""Tests for Permission model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Permission


@pytest.mark.asyncio
async def test_create_permission(db_session: AsyncSession):
    perm = Permission(name="read:logs", description="Can read logs")
    db_session.add(perm)
    await db_session.commit()
    await db_session.refresh(perm)
    assert perm.id is not None
    assert perm.name == "read:logs"


@pytest.mark.asyncio
async def test_permission_unique_name_constraint(db_session: AsyncSession):
    perm1 = Permission(name="unique:perm")
    perm2 = Permission(name="unique:perm")
    db_session.add_all([perm1, perm2])
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()
