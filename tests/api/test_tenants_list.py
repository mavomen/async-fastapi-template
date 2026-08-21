"""Tenant list endpoint tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.identity.crud.user import user as crud_user
from app.identity.schemas.user import UserCreate


@pytest.fixture
async def superuser_headers(db_session: AsyncSession) -> dict:
    user = await crud_user.create(
        db_session,
        obj_in=UserCreate(
            email="tenantlist@example.com",
            username="tenantlist",
            password="SuperPass1!",
        ),
    )
    user.is_superuser = True
    await db_session.commit()
    token = create_access_token(subject=user.id)
    return {"Authorization": f"Bearer {token}"}
