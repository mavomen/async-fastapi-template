"""Unit tests for CRUDBase edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Select

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
    with patch.object(crud, "get", AsyncMock(return_value=None)):
        result = await crud.delete(db, id=999)
        assert result is None


@pytest.mark.asyncio
async def test_get_multi_ordered_by_id():
    """CRUDBase.get_multi should generate SQL with ORDER BY."""
    model = MagicMock(spec=User)
    model.id = User.id
    crud = CRUDBase(model.__class__)

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result_mock)

    await crud.get_multi(db, skip=0, limit=10)

    call_args = db.execute.call_args[0][0]
    assert isinstance(call_args, Select)
    compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY" in compiled.upper()
