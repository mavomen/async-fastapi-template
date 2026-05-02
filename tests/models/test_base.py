"""Tests for base SQLAlchemy models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.models.base import Base


def test_base_is_declarative_base():
    """Verify Base is a proper declarative base."""
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


def test_base_metadata_naming_convention():
    """Verify metadata has naming conventions configured."""
    naming_convention = Base.metadata.naming_convention

    assert naming_convention is not None
    assert len(naming_convention) > 0

    assert "ix" in naming_convention


def test_base_metadata_exists():
    """Verify Base has metadata attribute."""
    assert hasattr(Base, "metadata")
    assert Base.metadata is not None


def test_base_is_subclassable():
    """Verify Base can be subclassed to create models."""
    from sqlalchemy import Column, Integer, String

    class TestModel(Base):
        __tablename__ = "test_model"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    assert hasattr(TestModel, "__tablename__")
    assert TestModel.__tablename__ == "test_model"
    assert hasattr(TestModel, "id")
    assert hasattr(TestModel, "name")


def test_base_subclass_has_table():
    """Verify subclasses have proper table inspection."""
    from sqlalchemy import Column, Integer, String, inspect

    class AnotherTestModel(Base):
        __tablename__ = "another_test"
        id = Column(Integer, primary_key=True)
        value = Column(String(100))

    mapper = inspect(AnotherTestModel)
    assert mapper is not None
    assert mapper.local_table.name == "another_test"


@pytest.mark.anyio
async def test_base_with_async_session(db_session):
    """Verify Base works with async sessions."""

    assert db_session is not None

    assert isinstance(db_session, AsyncSession)
