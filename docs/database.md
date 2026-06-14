# Database Layer Documentation

## Overview

The database layer provides async PostgreSQL connectivity using SQLAlchemy 2.0 with asyncpg driver. It implements connection pooling, session management, and proper async context manager patterns.

## Architecture

### Components

- **DatabaseSessionManager**: Singleton session manager with connection pooling
- **AsyncSession**: SQLAlchemy async session for database operations
- **Base**: Declarative base for ORM models
- **get_db()**: Dependency injection function for FastAPI routes

### Configuration

Database settings are managed through Pydantic Settings in `app/core/config.py`:

```python
class Settings(BaseSettings):
  DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi"
```

Environment variables:

- `DATABASE_URL`: PostgreSQL connection string with asyncpg driver

## Usage

### In FastAPI Routes

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
  result = await db.execute(select(User))
  return result.scalars().all()
```

### Direct Session Usage

```python
from app.core.database import sessionmanager

async with sessionmanager.session() as session:
result = await session.execute(select(User))
users = result.scalars().all()
```

### In Tests

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_database_operation(db_session: AsyncSession):
# db_session fixture provided by conftest.py
  result = await db_session.execute(select(User))
  assert result is not None
```

## Session Management

### Lifecycle

1. **Initialization**: `sessionmanager.init(DATABASE_URL)` creates engine and session factory
2. **Session Creation**: `async with sessionmanager.session()` provides isolated session
3. **Auto-commit**: Sessions commit automatically on successful context exit
4. **Auto-rollback**: Sessions rollback on exceptions
5. **Cleanup**: `await sessionmanager.close()` closes all connections

### Context Manager Pattern

The `session()` method uses `@asynccontextmanager` decorator:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def session(self) -> AsyncIterator[AsyncSession]:
if self._sessionmaker is None:
raise Exception("DatabaseSessionManager is not initialized")

session = self._sessionmaker()
try:
  yield session
except Exception:
  await session.rollback()
  raise
finally:
  await session.close()
```

## Connection Pooling

SQLAlchemy's connection pool is configured in `app/core/database.py`:

- **pool_size**: Number of persistent connections
- **max_overflow**: Additional connections when pool exhausted
- **pool_pre_ping**: Verify connections before use (enabled)

## Testing

### Test Database Setup

Tests use a separate test database configured in `tests/conftest.py`:

```python
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_test"
```

### Fixtures

- `db_session`: Provides clean AsyncSession for each test
- `test_db`: Manages test database lifecycle (create/drop tables)

### Running Tests

```bash
# Run all database tests
poetry run pytest tests/core/test_database.py -v

# Run with coverage
poetry run pytest tests/core/test_database.py --cov=app.core.database
```

## Migrations

Database migrations are managed with Alembic (async configuration).

### Commands

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

### Configuration

Alembic is configured for async operations in `alembic/env.py`:

- Uses `asyncpg` driver
- Imports `Base` metadata from models
- Runs migrations in async context

## Error Handling

### Common Issues

1. **Connection Refused**
   - Ensure PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify connection string in `.env`

2. **Session Not Initialized**
   - Call `sessionmanager.init(DATABASE_URL)` before use
   - Check application startup in `app/main.py`

3. **Async Context Manager Error**
   - Ensure `@asynccontextmanager` decorator is present
   - Use `async with` for session context

4. **Pool Exhausted**
   - Increase `DB_POOL_SIZE` or `DB_MAX_OVERFLOW`
   - Check for unclosed sessions in code

## Best Practices

1. **Always use dependency injection** (`Depends(get_db)`) in routes
2. **Never store sessions** as instance variables
3. **Use transactions** for multi-step operations
4. **Close sessions explicitly** in non-FastAPI contexts
5. **Use connection pooling** for production deployments
6. **Separate test and production databases**
7. **Run migrations** before deploying new versions

## Performance Considerations

- Connection pooling reduces overhead of creating new connections
- `pool_pre_ping` adds small latency but prevents stale connections
- Async operations allow handling multiple requests concurrently
- Use `selectinload()` or `joinedload()` to avoid N+1 queries

## Security

- Never commit `.env` files with production credentials
- Use environment variables for sensitive configuration
- Implement connection encryption for production (SSL/TLS)
- Use read-only database users for reporting queries
- Regularly rotate database passwords

## Monitoring

Key metrics to monitor:

- Connection pool utilization
- Query execution time
- Failed connection attempts
- Active session count
- Database CPU and memory usage

## References

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [FastAPI Database Guide](https://fastapi.tiangolo.com/tutorial/sql-databases/)
