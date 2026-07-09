# SPDX-License-Identifier: AGPL-3.0-only
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import Column, ColumnDefault, Table, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("ciaren.db")


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
    """Create missing tables (and missing columns) on startup.

    Idempotent and database-agnostic: ``create_all`` makes any missing tables,
    then we add columns that exist on the models but not yet in the database —
    useful for dev databases created before a column was introduced. The DDL is
    rendered by SQLAlchemy for the active dialect (SQLite / PostgreSQL / MySQL),
    so there is no hand-written, dialect-specific SQL.

    This is the zero-setup MVP path; a production deployment should manage schema
    changes through Alembic migrations instead. Additive DDL is best-effort and never
    blocks startup, but a failure is now *logged* (not silently swallowed) so schema
    drift is visible rather than hidden — see the loop below.
    """
    # Import models inside the function so they register on Base.metadata
    # without creating an import cycle (models import Base from this module).
    from app.db.models import (  # noqa: F401
        app_setting,
        connection,
        dataset,
        dataset_version,
        flow,
        project,
        run,
        schedule,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        statements = await conn.run_sync(_pending_column_ddl)

    # Each ADD COLUMN runs in its own transaction: on PostgreSQL a failing
    # statement aborts the whole transaction, so batching could roll back others.
    for stmt in statements:
        try:
            async with engine.begin() as conn:
                await conn.exec_driver_sql(stmt)
        except Exception:  # noqa: BLE001 - never block startup on additive DDL
            # Best-effort, but not silent: a swallowed failure here is exactly how
            # schema drift stays hidden until a query mysteriously fails later. Log
            # it (with the statement) so an operator can see a column didn't apply
            # and reach for a real Alembic migration.
            logger.warning("Additive schema migration failed for statement: %s", stmt, exc_info=True)


def _pending_column_ddl(connection: Connection) -> list[str]:
    """Return ``ALTER TABLE … ADD COLUMN`` statements for every column present on
    the models but missing from the live schema, rendered for this dialect."""
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    statements: list[str] = []
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue  # whole table was just created by create_all
        present = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in present:
                statements.append(_add_column_ddl(table, column, connection.dialect))
    return statements


def _add_column_ddl(table: Table, column: Column[Any], dialect: Dialect) -> str:
    parts = [f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(dialect=dialect)}"]
    default = _default_literal(column)
    if default is not None:
        parts.append(f"DEFAULT {default}")
    if not column.nullable:
        parts.append("NOT NULL")
    return " ".join(parts)


def _default_literal(column: Column[Any]) -> str | None:
    """Render a column's scalar Python default as a portable SQL literal, so a
    NOT NULL column can be added to a table that already has rows."""
    default = column.default
    if not isinstance(default, ColumnDefault) or not default.is_scalar:
        return None
    value = default.arg
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None
