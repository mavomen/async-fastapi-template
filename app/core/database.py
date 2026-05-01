"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


class DatabaseSessionManager:
    """Manages database engine and session lifecycle."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init(self, database_url: str) -> None:
        """Initialize database engine and session factory.

        Args:
            database_url: PostgreSQL connection string (asyncpg format)
        """
        self._engine = create_async_engine(
            database_url,
            echo=settings.ENVIRONMENT == "development",
            poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
            pool_pre_ping=True,
        )
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def close(self) -> None:
        """Close database engine and cleanup connections."""
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide async database session.

        Yields:
            AsyncSession: Database session for queries

        Raises:
            RuntimeError: If database not initialized
        """
        if self._sessionmaker is None:
            raise RuntimeError(
                "DatabaseSessionManager is not initialized. " "Call init() first."
            )
        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global session manager instance
sessionmanager = DatabaseSessionManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session
    """
    async with sessionmanager.session() as session:
        yield session
