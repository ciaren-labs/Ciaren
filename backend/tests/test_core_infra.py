"""Coverage for low-level infra: the database helpers and logging setup."""

import logging

import pytest
from sqlalchemy import Boolean, Column, Float, Integer, String, create_engine

from app.core import database as db_mod
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
