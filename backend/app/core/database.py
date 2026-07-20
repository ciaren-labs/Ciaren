# SPDX-License-Identifier: AGPL-3.0-only
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import Column, ColumnDefault, Table, event, inspect
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

# Recycle pooled server connections after this many seconds so a connection the
# database (or an intermediary like pgbouncer) may have already dropped is not
# handed to a request. Applied to networked backends only — see ``_make_engine``.
POOL_RECYCLE_SECONDS = 1800

# Alembic stamps the applied revision into this table. Its presence means the
# schema is migration-managed, so Ciaren's best-effort additive DDL must stand
# aside (see ``init_db``).
ALEMBIC_VERSION_TABLE = "alembic_version"


class Base(DeclarativeBase):
    pass


def enable_sqlite_foreign_keys(async_engine: AsyncEngine) -> None:
    """Turn on SQLite foreign-key enforcement for every connection of ``async_engine``.

    SQLite ships with ``PRAGMA foreign_keys`` OFF per connection, which silently
    turns every ``ondelete`` rule in the models into a no-op — deletes can leave
    dangling references (e.g. a purged dataset still pointed at by
    ``flow_runs.input_dataset_id``). PostgreSQL/MySQL always enforce foreign
    keys, so this listener registers only for SQLite, keeping all three backends
    consistent. The PRAGMA must run on each new DBAPI connection (it is
    connection-scoped, not database-scoped); this is the SQLAlchemy-documented
    pattern for async engines (listen on ``engine.sync_engine``).

    Deliberately NOT applied to the Alembic migration engine
    (``app/migrations/env.py`` builds its own): batch-mode migrations rebuild
    tables via drop/rename, which requires enforcement off.
    """
    if async_engine.sync_engine.dialect.name != "sqlite":
        return

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_sqlite_fk_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, Any] = {}
    if is_sqlite:
        connect_args = {"check_same_thread": False}
    else:
        # Networked backends (PostgreSQL/MySQL — the documented production path)
        # pool connections across requests. A pooled connection the server has
        # already closed (idle timeout, DB restart, pgbouncer) would otherwise be
        # handed to the next request and surface as a 500 (asyncpg
        # ConnectionDoesNotExistError / InterfaceError). ``pool_pre_ping`` checks
        # liveness on checkout and transparently replaces a dead connection;
        # ``pool_recycle`` proactively retires old ones. Deliberately NOT set for
        # SQLite, whose ``:memory:`` test DB has different pooling semantics.
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_recycle"] = POOL_RECYCLE_SECONDS
    made = create_async_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        **engine_kwargs,
    )
    enable_sqlite_foreign_keys(made)
    return made


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

    When the database is already Alembic-managed (an ``alembic_version`` table is
    present — the Docker entrypoint runs ``ciaren db upgrade`` before ``serve``),
    the best-effort ``ADD COLUMN`` patching is skipped: a migration may have
    deliberately shaped a column differently, and re-adding the model's version
    would diverge from the migration history. Alembic owns the schema there.
    ``create_all`` still runs — it is a no-op once the tables exist — so a fresh
    dev/quickstart SQLite DB (no ``alembic_version``) self-initializes exactly as
    before.
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
        alembic_managed = await conn.run_sync(_is_alembic_managed)
        statements = [] if alembic_managed else await conn.run_sync(_pending_column_ddl)

    if alembic_managed:
        logger.info(
            "Alembic-managed database detected (%s table present); skipping "
            "best-effort additive column DDL — migrations own the schema.",
            ALEMBIC_VERSION_TABLE,
        )
        return

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


def _is_alembic_managed(connection: Connection) -> bool:
    """True when the live schema carries Alembic's ``alembic_version`` table,
    i.e. migrations are the schema authority and additive DDL must stand aside."""
    return ALEMBIC_VERSION_TABLE in inspect(connection).get_table_names()


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
