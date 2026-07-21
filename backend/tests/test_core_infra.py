"""Coverage for low-level infra: the database helpers and logging setup."""

import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Boolean, Column, Float, Integer, String, create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import database as db_mod
from app.core.config import get_settings
from app.core.logging import setup_logging

# -- logging ------------------------------------------------------------


@pytest.mark.parametrize("environment", ["development", "production"])
def test_setup_logging(environment: str) -> None:
    setup_logging(environment)
    # The third-party loggers are quieted regardless of environment.
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


def test_json_log_format_emits_one_json_object_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    setup_logging("production", log_format="json")
    try:
        logging.getLogger("app.test").info("hello", extra={"run_id": "r1"})
        out = capsys.readouterr().out.strip().splitlines()
        record = json.loads(out[-1])
        assert record["level"] == "INFO"
        assert record["logger"] == "app.test"
        assert record["message"] == "hello"
        # Caller-supplied `extra=` fields are surfaced as top-level keys.
        assert record["run_id"] == "r1"
    finally:
        setup_logging("development")  # restore plain handler for other tests


def test_json_log_format_includes_exception_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    setup_logging("production", log_format="json")
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("app.test").exception("failed")
        record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "ValueError: boom" in record["exception"]
    finally:
        setup_logging("development")


# -- database: session + schema helpers ---------------------------------


async def test_get_db_yields_session() -> None:
    gen = db_mod.get_db()
    session = await gen.__anext__()
    assert session is not None
    await gen.aclose()


async def test_init_db_is_idempotent() -> None:
    # Runs create_all + the additive-column pass twice; must not raise.
    await db_mod.init_db()
    await db_mod.init_db()


async def test_init_db_logs_additive_ddl_failure_but_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # A failing additive migration must NOT block startup, but must be logged (not
    # silently swallowed) so schema drift is visible.
    monkeypatch.setattr(
        db_mod,
        "_pending_column_ddl",
        lambda conn: ["ALTER TABLE no_such_table ADD COLUMN x INTEGER"],
    )
    with caplog.at_level(logging.WARNING, logger="ciaren.db"):
        await db_mod.init_db()  # must not raise
    assert any("Additive schema migration failed" in r.message for r in caplog.records)


# -- database: engine pool settings (F1) --------------------------------


def _capture_make_engine_kwargs(monkeypatch: pytest.MonkeyPatch, url: str) -> dict[str, object]:
    """Build the app engine with ``create_async_engine`` mocked and return the
    kwargs it was called with, without opening a real connection."""
    captured: dict[str, object] = {}

    def _fake_create(url_arg: str, **kwargs: object) -> MagicMock:
        captured["url"] = url_arg
        captured.update(kwargs)
        # A non-sqlite MagicMock makes enable_sqlite_foreign_keys() return early.
        return MagicMock()

    monkeypatch.setenv("CIAREN_DATABASE_URL", url)
    get_settings.cache_clear()
    monkeypatch.setattr(db_mod, "create_async_engine", _fake_create)
    try:
        db_mod._make_engine()
    finally:
        get_settings.cache_clear()
    return captured


def test_make_engine_enables_pool_pre_ping_for_networked_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres/MySQL (the documented prod path) pool connections across requests;
    a server-closed connection must not surface as a 500. The factory must pass
    ``pool_pre_ping`` + a ``pool_recycle`` for non-SQLite URLs."""
    kwargs = _capture_make_engine_kwargs(monkeypatch, "postgresql+asyncpg://u:p@db.internal/ciaren")
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_recycle"] == db_mod.POOL_RECYCLE_SECONDS


def test_make_engine_omits_pool_settings_for_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite (incl. the in-memory test DB) keeps its exact existing behavior: no
    pool_pre_ping / pool_recycle, only the check_same_thread connect arg."""
    kwargs = _capture_make_engine_kwargs(monkeypatch, "sqlite+aiosqlite:///:memory:")
    assert "pool_pre_ping" not in kwargs
    assert "pool_recycle" not in kwargs
    assert kwargs["connect_args"] == {"check_same_thread": False}


# -- database: Alembic-managed schema gating (F2) -----------------------


def _spy_pending_column_ddl(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Wrap ``_pending_column_ddl`` so tests can see whether the additive-DDL
    pass ran, while preserving its real return value."""
    calls: list[int] = []
    real = db_mod._pending_column_ddl

    def _wrapper(connection: object) -> list[str]:
        calls.append(1)
        return real(connection)  # type: ignore[arg-type]

    monkeypatch.setattr(db_mod, "_pending_column_ddl", _wrapper)
    return calls


async def test_init_db_skips_additive_ddl_when_alembic_managed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When an ``alembic_version`` table exists the DB is migration-managed, so
    init_db must NOT run best-effort ADD COLUMN patching (it would diverge from
    the migration history). A skip line is logged for observability."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db_mod, "engine", eng)
    calls = _spy_pending_column_ddl(monkeypatch)
    try:
        async with eng.begin() as conn:
            await conn.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        with caplog.at_level(logging.INFO, logger="ciaren.db"):
            await db_mod.init_db()
        assert calls == []  # additive-DDL pass was skipped entirely
        assert any("Alembic-managed database detected" in r.message for r in caplog.records)
    finally:
        await eng.dispose()


async def test_init_db_runs_additive_ddl_on_fresh_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh/dev DB (no alembic_version — the default SQLite quickstart) still
    self-initializes exactly as before: create_all + the additive-DDL pass run
    and the schema is created."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(db_mod, "engine", eng)
    calls = _spy_pending_column_ddl(monkeypatch)
    try:
        await db_mod.init_db()
        assert calls  # additive-DDL pass ran (fresh, unmanaged DB)
        async with eng.connect() as conn:
            names = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert "projects" in names  # schema was initialized
        assert "alembic_version" not in names
    finally:
        await eng.dispose()


def test_default_literal_renders_each_scalar_type() -> None:
    assert db_mod._default_literal(Column("a", Integer, default=5)) == "5"
    assert db_mod._default_literal(Column("b", Float, default=1.5)) == "1.5"
    assert db_mod._default_literal(Column("c", Boolean, default=True)) == "TRUE"
    assert db_mod._default_literal(Column("d", Boolean, default=False)) == "FALSE"
    assert db_mod._default_literal(Column("e", String, default="it's")) == "'it''s'"
    assert db_mod._default_literal(Column("f", Integer)) is None  # no default
    assert db_mod._default_literal(Column("g", Integer, default=lambda: 1)) is None  # callable


def test_pending_column_ddl_detects_missing_columns() -> None:
    # Ensure the models are registered on Base.metadata.
    from app.db.models import (  # noqa: F401
        dataset,
        dataset_version,
        flow,
        project,
        run,
        schedule,
    )

    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        # A 'projects' table that is missing most of the model's columns.
        conn.exec_driver_sql("CREATE TABLE projects (id VARCHAR)")
        statements = db_mod._pending_column_ddl(conn)

    project_alters = [s for s in statements if s.startswith("ALTER TABLE projects ADD COLUMN")]
    assert project_alters  # at least one missing column was detected
    # The rendered DDL carries type info and (for NOT NULL defaults) a DEFAULT clause.
    assert any("DEFAULT" in s for s in project_alters)


# -- version ------------------------------------------------------------


def test_ciaren_version_returns_installed_metadata() -> None:
    from app import version as version_mod

    assert version_mod.ciaren_version()  # non-empty either way


def test_ciaren_version_falls_back_when_metadata_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any metadata-backend failure falls back — not only the stdlib
    PackageNotFoundError (backport finders raise their own exception types),
    so a broken environment can never block plugin loading."""
    from app import version as version_mod

    class MetadataNotFound(Exception):  # mimics importlib_metadata's exception
        pass

    def _raise(name: str) -> str:
        raise MetadataNotFound(name)

    monkeypatch.setattr(version_mod, "version", _raise)
    assert version_mod.ciaren_version() == version_mod._FALLBACK


@pytest.mark.parametrize("bogus", [None, ""])
def test_ciaren_version_falls_back_when_metadata_returns_no_version(
    monkeypatch: pytest.MonkeyPatch, bogus: str | None
) -> None:
    """A stale/broken dist-info can make ``version()`` return None (a missing
    Version field) instead of raising — the promised string fallback must hold,
    or plugin compatibility checks downstream crash on ``Version(None)``."""
    from app import version as version_mod

    monkeypatch.setattr(version_mod, "version", lambda name: bogus)
    assert version_mod.ciaren_version() == version_mod._FALLBACK
