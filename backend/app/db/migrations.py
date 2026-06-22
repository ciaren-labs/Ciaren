"""Programmatic Alembic access for the ``flowframe db`` commands.

Builds an Alembic ``Config`` pointing at the migration environment packaged
under ``app/migrations``, so it resolves identically from a source checkout and
from a ``pip``-installed wheel. The database URL always comes from ``Settings``
(``env.py`` reads it), so these helpers honour ``--env-file`` and
``FLOWFRAME_DATABASE_URL``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from alembic.config import Config


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "migrations"


def _app_table_names() -> set[str]:
    """Tables the application owns, so we can tell a real DB from an empty one
    without depending on a hardcoded list."""
    from app.core.database import Base

    # Importing the models registers them on Base.metadata.
    from app.db.models import (  # noqa: F401
        dataset,
        dataset_version,
        flow,
        project,
        run,
        schedule,
    )

    return set(Base.metadata.tables.keys())


def make_alembic_config() -> "Config":
    from alembic.config import Config

    from app.core.config import get_settings

    cfg = Config()
    cfg.set_main_option("script_location", str(_migrations_dir()))
    # env.py reads the URL from Settings; mirror it here so offline tooling and
    # any logging that echoes the config agree on the target database.
    cfg.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
    return cfg


def _inspect_state(url: str) -> tuple[bool, bool]:
    """Return ``(has_alembic_version, has_app_tables)`` for the live database."""
    app_tables = _app_table_names()

    async def _run() -> tuple[bool, bool]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:

                def check(sync_conn: Connection) -> tuple[bool, bool]:
                    names = set(inspect(sync_conn).get_table_names())
                    return ("alembic_version" in names, bool(app_tables & names))

                return await conn.run_sync(check)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def upgrade(revision: str = "head") -> bool:
    """Apply migrations up to ``revision``. Safe to re-run.

    If the database already has the application tables but no ``alembic_version``
    row, it was bootstrapped by the startup ``create_all`` path before migrations
    were managed. We *adopt* it by stamping the current head instead of letting
    Alembic try to re-create tables that already exist. ``create_all`` always
    builds the latest schema on startup, so stamping head matches what is on
    disk. Returns ``True`` when an existing schema was adopted this way.
    """
    from alembic import command

    from app.core.config import get_settings

    cfg = make_alembic_config()
    has_version, has_tables = _inspect_state(get_settings().DATABASE_URL)

    adopted = False
    if not has_version and has_tables:
        command.stamp(cfg, "head")
        adopted = True

    command.upgrade(cfg, revision)
    return adopted


def current() -> None:
    """Print the revision the database is currently stamped at."""
    from alembic import command

    command.current(make_alembic_config(), verbose=True)


def reset() -> None:
    """Drop every table (including ``alembic_version``) and rebuild from
    migrations. Robust regardless of the database's prior migration state."""
    from alembic import command

    from app.core.config import get_settings
    from app.core.database import Base

    _app_table_names()  # ensure models are registered on Base.metadata

    async def _drop_all(url: str) -> None:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        finally:
            await engine.dispose()

    asyncio.run(_drop_all(get_settings().DATABASE_URL))
    command.upgrade(make_alembic_config(), "head")
