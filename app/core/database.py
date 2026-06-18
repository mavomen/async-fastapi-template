"""Database configuration and session management with read/write split."""

import logging
import time
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import Delete, Insert, Select, Update

from app.core.config import settings
from app.core.metrics import (
    db_connections_total,
    db_pool_saturation_ratio,
    db_reader_connections_total,
)
from app.core.tenant import get_current_tenant

logger = logging.getLogger("app.db")

query_count_var: ContextVar[int] = ContextVar("query_count", default=0)


def _make_engine_kwargs() -> dict[str, Any]:
    """Build engine kwargs from settings (shared by writer and reader)."""
    kwargs: dict[str, Any] = {
        "echo": settings.ENVIRONMENT == "development",
        "pool_pre_ping": True,
    }
    if settings.ENVIRONMENT == "test":
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    return kwargs


def _install_engine_listeners(engine: AsyncEngine, pool_label: str) -> None:
    """Install slow-query, query-count, and tenant-RLS listeners on an engine."""

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(  # type: ignore[no-untyped-def]  # noqa: PLR0913
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info["query_start_time"] = time.monotonic()
        query_count_var.set(query_count_var.get() + 1)

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(  # type: ignore[no-untyped-def]  # noqa: PLR0913
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
                        "pool": pool_label,
                    },
                )

    @event.listens_for(engine.sync_engine, "before_execute", retval=True)
    def _add_tenant_filter(  # type: ignore[no-untyped-def]
        conn, clauseelement, multiparams, params, execution_options
    ):
        tenant_id = get_current_tenant()
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


class DatabaseSessionManager:
    """Manages writer and reader database engines and session lifecycle."""

    def __init__(self) -> None:
        self._writer_engine: AsyncEngine | None = None
        self._reader_engine: AsyncEngine | None = None
        self._writer_sessionmaker: async_sessionmaker[AsyncSession] | None = None
        self._reader_sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init(self, writer_url: str, reader_url: str | None = None) -> None:
        """Initialize writer and optional reader database engines.

        Args:
            writer_url: Primary database connection string.
            reader_url: Read-replica connection string. Falls back to writer_url when unset.
        """
        reader_url = reader_url or writer_url

        engine_kwargs = _make_engine_kwargs()

        self._writer_engine = create_async_engine(writer_url, **engine_kwargs)
        _install_engine_listeners(self._writer_engine, pool_label="writer")

        self._reader_engine = create_async_engine(reader_url, **engine_kwargs)
        _install_engine_listeners(self._reader_engine, pool_label="reader")

        self._writer_sessionmaker = async_sessionmaker(
            bind=self._writer_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        self._reader_sessionmaker = async_sessionmaker(
            bind=self._reader_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    async def close(self) -> None:
        """Close both database engines and cleanup connections."""
        if self._writer_engine is not None:
            await self._writer_engine.dispose()
            self._writer_engine = None
            self._writer_sessionmaker = None
        if self._reader_engine is not None:
            await self._reader_engine.dispose()
            self._reader_engine = None
            self._reader_sessionmaker = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Provide a writer database session (legacy alias for backward compatibility)."""
        async with self.writer_session() as session:
            yield session

    @asynccontextmanager
    async def writer_session(self) -> AsyncIterator[AsyncSession]:
        """Provide a writer database session (routes to primary)."""
        if self._writer_sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized. Call init() first.")
        async with self._writer_sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def reader_session(self) -> AsyncIterator[AsyncSession]:
        """Provide a read-only database session (routes to replica)."""
        if self._reader_sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized. Call init() first.")
        async with self._reader_sessionmaker() as session:
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
    """FastAPI dependency for writer database sessions."""
    db_connections_total.inc()
    try:
        async with sessionmanager.writer_session() as session:
            yield session
    finally:
        db_connections_total.dec()
        _report_pool_saturation("writer")


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for read-only database sessions (routes to replica)."""
    db_reader_connections_total.inc()
    try:
        async with sessionmanager.reader_session() as session:
            yield session
    finally:
        db_reader_connections_total.dec()
        _report_pool_saturation("reader")


def _report_pool_saturation(pool: str) -> None:
    """Log and expose pool saturation ratio if above threshold."""
    engine = sessionmanager._writer_engine if pool == "writer" else sessionmanager._reader_engine
    if engine is None:
        return

    pool_instance = engine.pool
    pool_size = getattr(pool_instance, "size", None)
    pool_checkedin = getattr(pool_instance, "checkedin", None)
    if pool_size is not None and pool_checkedin is not None:
        total = pool_size()
        active = pool_checkedin()
        if total > 0:
            ratio = 1.0 - (active / total)
            db_pool_saturation_ratio.labels(pool=pool).set(ratio)
            if ratio >= settings.DB_POOL_SATURATION_THRESHOLD:
                logger.warning(
                    "Database pool saturation above threshold",
                    extra={
                        "pool": pool,
                        "ratio": round(ratio, 2),
                        "threshold": settings.DB_POOL_SATURATION_THRESHOLD,
                    },
                )


def apply_tenant_filter(
    tenant_id: int | None, clauseelement: Any, multiparams: Any, params: Any, execution_options: Any
) -> Any:
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
