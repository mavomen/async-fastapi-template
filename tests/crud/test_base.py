"""Unit tests for CRUDBase edge cases."""

from unittest.mock import AsyncMock, patch

import pytest

from app.crud.base import CRUDBase
from app.models.user import User


@pytest.mark.asyncio
async def test_update_with_dict():
    """CRUDBase.update should accept a plain dict."""
    crud = CRUDBase(User)
    db = AsyncMock()
    db_obj = User(id=1, email="test@test.com", username="test", hashed_password="x")
    with patch.object(crud, "get", return_value=db_obj):
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        result = await crud.update(db, db_obj=db_obj, obj_in={"full_name": "Updated"})
        assert result.full_name == "Updated"


@pytest.mark.asyncio
async def test_delete_returns_none_if_not_found():
    """CRUDBase.delete should return None when the object doesn't exist."""
    crud = CRUDBase(User)
    db = AsyncMock()
    # Mock the get method to return None
    with patch.object(crud, "get", AsyncMock(return_value=None)):
        result = await crud.delete(db, id=999)
        assert result is None
