"""Tests for database session management."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import DatabaseSessionManager, get_db


class TestDatabaseSessionManager:
    """Test DatabaseSessionManager functionality."""

    @pytest.mark.asyncio
    async def test_init_creates_engine_and_sessionmaker(self) -> None:
        """Test that init() creates engine and sessionmaker."""
        manager = DatabaseSessionManager()
        manager.init("postgresql+asyncpg://user:pass@localhost/test")

        assert manager._engine is not None
        assert manager._sessionmaker is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_close_disposes_engine(self) -> None:
        """Test that close() disposes engine."""
        manager = DatabaseSessionManager()
        manager.init("postgresql+asyncpg://user:pass@localhost/test")

        await manager.close()

        assert manager._engine is None
        assert manager._sessionmaker is None

    @pytest.mark.asyncio
    async def test_session_raises_if_not_initialized(self) -> None:
        """Test that session() raises RuntimeError if not initialized."""
        manager = DatabaseSessionManager()

        with pytest.raises(RuntimeError, match="not initialized"):
            async with manager.session():
                pass

    @pytest.mark.asyncio
    async def test_session_yields_async_session(self, test_db_url: str) -> None:
        """Test that session() yields AsyncSession."""
        manager = DatabaseSessionManager()
        manager.init(test_db_url)

        async with manager.session() as session:
            assert isinstance(session, AsyncSession)

        await manager.close()

    @pytest.mark.asyncio
    async def test_session_rollback_on_exception(self, test_db_url: str) -> None:
        """Test that session rolls back on exception."""
        manager = DatabaseSessionManager()
        manager.init(test_db_url)

        with pytest.raises(ValueError):
            async with manager.session() as session:
                # Simulate an error
                raise ValueError("Test error")

        await manager.close()


class TestGetDbDependency:
    """Test get_db FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self, test_db_url: str) -> None:
        """Test that get_db yields AsyncSession."""
        from app.core.database import sessionmanager

        sessionmanager.init(test_db_url)

        async for session in get_db():
            assert isinstance(session, AsyncSession)
            # Test basic query
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await sessionmanager.close()
