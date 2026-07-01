"""
Pytest configuration and fixtures for Ciaren backend tests.

Supports testing against different database backends:
- SQLite (default, no setup needed)
- PostgreSQL (via DATABASE_URL environment variable)
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get database URL from environment or use SQLite default."""
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    # Normalize SQLite URLs for testing
    if "sqlite" in url and ":memory:" not in url:
        # Replace file path with in-memory for faster tests
        url = "sqlite+aiosqlite:///:memory:"

    # For PostgreSQL, ensure it uses async driver
    if "postgresql://" in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    elif "postgres://" in url:
        url = url.replace("postgres://", "postgresql+asyncpg://")

    return url


@pytest.fixture
async def engine(database_url):
    """Create a test database engine."""
    async_engine = create_async_engine(
        database_url,
        echo=False,
        poolclass=NullPool,  # No connection pooling in tests
    )

    # Create all tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_engine

    # Drop all tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await async_engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async_session = AsyncSession(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    try:
        yield async_session
    finally:
        await async_session.close()


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"
