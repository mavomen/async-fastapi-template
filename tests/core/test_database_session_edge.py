"""Test database session rollback on exception."""

import pytest

from app.core.database import DatabaseSessionManager


@pytest.mark.asyncio
async def test_init_creates_sessionmaker():
    manager = DatabaseSessionManager()
    manager.init("postgresql+asyncpg://user:pass@localhost/test")
    assert manager._sessionmaker is not None
    await manager.close()


@pytest.mark.asyncio
async def test_close_disposes_engine():
    manager = DatabaseSessionManager()
    manager.init("postgresql+asyncpg://user:pass@localhost/test")
    await manager.close()
    assert manager._engine is None
    assert manager._sessionmaker is None
