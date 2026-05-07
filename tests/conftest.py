"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Set test environment variables before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-min-32-characters-long"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test"
)

from app.core.database import sessionmanager
from app.main import app
from app.models.base import Base


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Provide test database URL."""
    return os.environ["DATABASE_URL"]


@pytest.fixture(scope="function")
async def db_engine(test_db_url: str) -> AsyncGenerator[Any, None]:
    """Create test database engine."""
    engine = create_async_engine(test_db_url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Provide test database session."""
    # Ensure the session manager points to the test database
    sessionmanager.init(os.environ["DATABASE_URL"])

    async with sessionmanager.session() as session:
        yield session

    # Do NOT close the sessionmanager here – it might still be used by other fixtures.


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Provide synchronous test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide asynchronous test client with sessionmanager initialized."""
    sessionmanager.init(os.environ["DATABASE_URL"])
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac
    await sessionmanager.close()
