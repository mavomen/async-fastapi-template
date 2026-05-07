"""Database configuration and session management."""

import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.metrics import db_connections_total

logger = logging.getLogger("app.db")


class DatabaseSessionManager:
    """Manages database engine and session lifecycle."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init(self, database_url: str) -> None:
        """Initialize database engine and session factory."""
        engine_kwargs: dict = {
            "echo": settings.ENVIRONMENT == "development",
            "pool_pre_ping": True,
        }

        if settings.ENVIRONMENT == "test":
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = 20
            engine_kwargs["max_overflow"] = 10
            engine_kwargs["pool_recycle"] = 3600

        self._engine = create_async_engine(database_url, **engine_kwargs)

        # Add slow query profiling on the sync engine
        @event.listens_for(self._engine.sync_engine, "before_cursor_execute")
        def _before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            conn.info["query_start_time"] = time.monotonic()

        @event.listens_for(self._engine.sync_engine, "after_cursor_execute")
        def _after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            start = conn.info.pop("query_start_time", None)
            if start is not None:
                duration_ms = (time.monotonic() - start) * 1000
                if duration_ms > getattr(settings, "SLOW_QUERY_THRESHOLD_MS", 500):
                    logger.warning(
                        "Slow query detected",
                        extra={
                            "duration_ms": round(duration_ms, 2),
                            "statement": statement,
                        },
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

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide async database session."""
        if self._sessionmaker is None:
            raise RuntimeError(
                "DatabaseSessionManager is not initialized. Call init() first."
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
    """FastAPI dependency for database sessions."""
    db_connections_total.inc()
    try:
        async with sessionmanager.session() as session:
            yield session
    finally:
        db_connections_total.dec()
