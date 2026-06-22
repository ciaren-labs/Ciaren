from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=settings.DEBUG,
    )


engine = _make_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create any missing tables on startup.

    Idempotent (only creates tables that don't exist), so it's safe to run on
    every boot. This is the MVP convenience path; a production deployment should
    manage schema changes through Alembic migrations instead.
    """
    # Import models inside the function so they register on Base.metadata
    # without creating an import cycle (models import Base from this module).
    from app.db.models import dataset, dataset_version, flow, project, run  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe migrations: add columns to existing databases that predate them.
        for stmt in [
            "ALTER TABLE datasets ADD COLUMN dataset_kind TEXT DEFAULT 'input'",
            "ALTER TABLE dataset_versions ADD COLUMN source_run_id TEXT",
        ]:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # Column already present — nothing to do
