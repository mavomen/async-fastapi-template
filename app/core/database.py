"""Database configuration and session management."""

import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import Delete, Insert, Select, Update

from app.core.config import settings
from app.core.metrics import db_connections_total
from app.core.tenant import get_current_tenant

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
        def _before_cursor_execute(  # noqa: PLR0913
            conn, cursor, statement, parameters, context, executemany
        ):
            conn.info["query_start_time"] = time.monotonic()

        @event.listens_for(self._engine.sync_engine, "after_cursor_execute")
        def _after_cursor_execute(  # noqa: PLR0913
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

        # Add Row-Level Security (tenant isolation)
        @event.listens_for(self._engine.sync_engine, "before_execute", retval=True)
        def _add_tenant_filter(
            conn, clauseelement, multiparams, params, execution_options
        ):
            tenant_id = get_current_tenant()
            if tenant_id is None:
                return clauseelement, multiparams, params

            if isinstance(clauseelement, Select):
                for table in clauseelement.get_final_froms():
                    if hasattr(table, "columns") and "tenant_id" in table.columns:
                        clauseelement = clauseelement.where(
                            table.c.tenant_id == tenant_id
                        )
                        break
            elif isinstance(clauseelement, Insert):
                table = clauseelement.table
                if table.columns.get("tenant_id") is not None:
                    existing = getattr(clauseelement, "_values", {}) or {}
                    if "tenant_id" not in existing:
                        clauseelement = clauseelement.values(tenant_id=tenant_id)
            elif isinstance(clauseelement, Update) or isinstance(clauseelement, Delete):
                table = clauseelement.table
                if "tenant_id" in table.columns.keys():
                    clauseelement = clauseelement.where(table.c.tenant_id == tenant_id)

            return clauseelement, multiparams, params

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


def apply_tenant_filter(
    tenant_id: int | None, clauseelement, multiparams, params, execution_options
):
    """Public helper that applies tenant-RLS filter (callable from tests)."""
    if tenant_id is None:
        return clauseelement, multiparams, params

    if isinstance(clauseelement, Select):
        for table in clauseelement.get_final_froms():
            if hasattr(table, "columns") and "tenant_id" in table.columns:
                clauseelement = clauseelement.where(table.c.tenant_id == tenant_id)
                break
    elif isinstance(clauseelement, Insert):
        table = clauseelement.table
        if table.columns.get("tenant_id") is not None:
            existing = getattr(clauseelement, "_values", {}) or {}
            if "tenant_id" not in existing:
                clauseelement = clauseelement.values(tenant_id=tenant_id)
    elif isinstance(clauseelement, Update) or isinstance(clauseelement, Delete):
        table = clauseelement.table
        if "tenant_id" in table.columns.keys():
            clauseelement = clauseelement.where(table.c.tenant_id == tenant_id)

    return clauseelement, multiparams, params
