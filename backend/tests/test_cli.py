"""Tests for the `ciaren` CLI entry point.

These exercise argument parsing, env wiring, and the helper commands without
booting a real server (uvicorn.run is stubbed) or mutating real config/DB files.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

import pytest

from app import cli


def _clear_settings_cache() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()


# -- serve: parsing + env wiring ---------------------------------------


def test_serve_defaults() -> None:
    args = cli.build_parser().parse_args(["serve"])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8055
    assert args.reload is False
    assert args.no_scheduler is False
    assert args.db_url is None
    assert args.data_dir is None
    assert args.engine is None
    assert args.execution_mode is None
    assert args.log_level is None
    assert args.env_file is None


def test_serve_flags_are_parsed() -> None:
    args = cli.build_parser().parse_args(
        [
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--reload",
            "--no-scheduler",
            "--db-url",
            "sqlite+aiosqlite:///x.db",
            "--data-dir",
            "/tmp/ciaren",
            "--engine",
            "pandas",
            "--execution-mode",
            "process",
            "--log-level",
            "debug",
        ]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.reload is True
    assert args.no_scheduler is True
    assert args.db_url == "sqlite+aiosqlite:///x.db"
    assert args.data_dir == "/tmp/ciaren"
    assert args.engine == "pandas"
    assert args.execution_mode == "process"
    assert args.log_level == "debug"


def test_run_seed_flows_flag() -> None:
    assert cli.build_parser().parse_args(["serve"]).run_seed_flows is False
    assert cli.build_parser().parse_args(["serve", "--run-seed-flows"]).run_seed_flows is True


def test_apply_serve_env_sets_run_seed_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIAREN_SEED_RUN_FLOWS", raising=False)
    args = argparse.Namespace(
        db_url=None,
        data_dir=None,
        engine=None,
        execution_mode=None,
        no_scheduler=False,
        no_demo=False,
        run_seed_flows=True,
    )
    cli._apply_serve_env(args)
    assert os.environ["CIAREN_SEED_RUN_FLOWS"] == "true"


def test_engine_choice_is_validated() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--engine", "spark"])


def test_apply_serve_env_sets_all_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CIAREN_DATABASE_URL",
        "CIAREN_DATA_DIR",
        "CIAREN_DEFAULT_ENGINE",
        "CIAREN_EXECUTION_MODE",
        "CIAREN_SCHEDULER_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    args = argparse.Namespace(
        db_url="postgresql+asyncpg://x",
        data_dir="/data/ciaren",
        engine="pandas",
        execution_mode="process",
        no_scheduler=True,
    )

    cli._apply_serve_env(args)

    assert os.environ["CIAREN_DATABASE_URL"] == "postgresql+asyncpg://x"
    assert os.environ["CIAREN_DATA_DIR"] == "/data/ciaren"
    assert os.environ["CIAREN_DEFAULT_ENGINE"] == "pandas"
    assert os.environ["CIAREN_EXECUTION_MODE"] == "process"
    assert os.environ["CIAREN_SCHEDULER_ENABLED"] == "false"


def test_apply_serve_env_noop_without_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIAREN_DATABASE_URL", raising=False)
    monkeypatch.delenv("CIAREN_SCHEDULER_ENABLED", raising=False)
    args = argparse.Namespace(db_url=None, data_dir=None, engine=None, execution_mode=None, no_scheduler=False)

    cli._apply_serve_env(args)

    assert "CIAREN_DATABASE_URL" not in os.environ
    assert "CIAREN_SCHEDULER_ENABLED" not in os.environ


def test_main_serve_invokes_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, **kwargs: object) -> None:
        captured["app_path"] = app_path
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    cli.main(["serve", "--host", "0.0.0.0", "--port", "9100", "--log-level", "warning"])

    assert captured["app_path"] == "app.main:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9100
    assert captured["reload"] is False
    assert captured["log_level"] == "warning"


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main([])
    out = capsys.readouterr().out
    assert "usage: ciaren" in out
    assert "serve" in out


# -- env file -----------------------------------------------------------


def test_env_file_is_parsed_for_serve_info_check() -> None:
    for command in ("serve", "info", "check"):
        args = cli.build_parser().parse_args([command, "--env-file", "/tmp/custom.env"])
        assert args.env_file == "/tmp/custom.env"


def test_load_env_file_noop_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CIAREN_DEFAULT_ENGINE", raising=False)
    cli._load_env_file(argparse.Namespace(env_file=None))
    assert "CIAREN_DEFAULT_ENGINE" not in os.environ


def test_load_env_file_loads_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CIAREN_DEFAULT_ENGINE", raising=False)
    env = tmp_path / "custom.env"
    env.write_text("CIAREN_DEFAULT_ENGINE=pandas\n", encoding="utf-8")

    cli._load_env_file(argparse.Namespace(env_file=str(env)))

    assert os.environ["CIAREN_DEFAULT_ENGINE"] == "pandas"


def test_load_env_file_does_not_override_existing_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CIAREN_DEFAULT_ENGINE", "polars")
    env = tmp_path / "custom.env"
    env.write_text("CIAREN_DEFAULT_ENGINE=pandas\n", encoding="utf-8")

    cli._load_env_file(argparse.Namespace(env_file=str(env)))

    assert os.environ["CIAREN_DEFAULT_ENGINE"] == "polars"


def test_load_env_file_missing_path_exits() -> None:
    with pytest.raises(SystemExit):
        cli._load_env_file(argparse.Namespace(env_file="/no/such/file.env"))


# -- info ---------------------------------------------------------------


def test_info_prints_and_redacts_password(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("CIAREN_DATABASE_URL", "postgresql+asyncpg://user:s3cret@host/db")
    _clear_settings_cache()
    try:
        cli.main(["info"])
    finally:
        _clear_settings_cache()
    out = capsys.readouterr().out
    assert "default_engine" in out
    assert "data_dir" in out
    assert "user:***@host" in out
    assert "s3cret" not in out


def test_info_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    _clear_settings_cache()
    try:
        cli.main(["info", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    assert data["app_name"] == "Ciaren"
    assert data["default_engine"] in ("polars", "pandas")


# -- check --------------------------------------------------------------


def test_check_passes_with_reachable_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))
    _clear_settings_cache()
    try:
        cli.main(["check"])  # must not raise
    finally:
        _clear_settings_cache()
    out = capsys.readouterr().out
    assert "All checks passed" in out
    assert "[FAIL]" not in out


def test_check_json_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))
    _clear_settings_cache()
    try:
        cli.main(["check", "--output", "json"])
    finally:
        _clear_settings_cache()
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert {c["name"] for c in data["checks"]} >= {"data_dir", "database", "engines"}


def test_check_fails_when_db_unreachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CIAREN_DATA_DIR", str(tmp_path))

    def boom(_url: str) -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(cli, "_probe_database", boom)
    _clear_settings_cache()
    try:
        with pytest.raises(SystemExit) as exc:
            cli.main(["check"])
    finally:
        _clear_settings_cache()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] database" in out
    assert "connection refused" in out


# -- db -----------------------------------------------------------------


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _table_names(db: Path) -> set[str]:
    con = sqlite3.connect(db)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_db_upgrade_creates_schema_from_migrations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = tmp_path / "ciaren.db"
    monkeypatch.setenv("CIAREN_DATABASE_URL", _sqlite_url(db))
    _clear_settings_cache()
    try:
        cli.main(["db", "upgrade"])
    finally:
        _clear_settings_cache()
    names = _table_names(db)
    assert {"projects", "flows", "flow_runs", "schedules", "alembic_version"} <= names


def test_db_upgrade_adopts_create_all_schema(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A DB with the app tables but no alembic_version (bootstrapped by the
    startup create_all) must be adopted, not have its tables re-created."""
    db = tmp_path / "ciaren.db"
    monkeypatch.setenv("CIAREN_DATABASE_URL", _sqlite_url(db))
    _clear_settings_cache()
    try:
        cli.main(["db", "upgrade"])  # build full schema + version table
        con = sqlite3.connect(db)
        con.execute("DROP TABLE alembic_version")  # simulate create_all-only DB
        con.commit()
        con.close()
        capsys.readouterr()  # discard first run's output
        cli.main(["db", "upgrade"])  # must adopt, not recreate
    finally:
        _clear_settings_cache()
    out = capsys.readouterr().out.lower()
    assert "adopted" in out
    assert "alembic_version" in _table_names(db)


def test_db_reset_requires_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.db.migrations.reset", lambda: None)
    _clear_settings_cache()
    try:
        with pytest.raises(SystemExit):
            cli.main(["db", "reset"])
    finally:
        _clear_settings_cache()


def test_db_reset_refuses_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CIAREN_ENVIRONMENT", "production")
    monkeypatch.setattr("app.db.migrations.reset", lambda: None)
    _clear_settings_cache()
    try:
        with pytest.raises(SystemExit):
            cli.main(["db", "reset", "--yes"])
    finally:
        _clear_settings_cache()


def test_db_reset_runs_with_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {}
    monkeypatch.setattr("app.db.migrations.reset", lambda: called.setdefault("ran", True))
    _clear_settings_cache()
    try:
        cli.main(["db", "reset", "--yes"])
    finally:
        _clear_settings_cache()
    assert called.get("ran") is True


def test_db_env_file_is_parsed() -> None:
    for command in ("upgrade", "current", "reset"):
        args = cli.build_parser().parse_args(["db", command, "--env-file", "/tmp/x.env"])
        assert args.env_file == "/tmp/x.env"


# -- transformations ----------------------------------------------------


def test_transformations_list_table(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["transformations", "list"])
    out = capsys.readouterr().out
    assert "transformation node types" in out
    assert "dropNulls" in out


def test_transformations_list_json(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["transformations", "list", "--output", "json"])
    data = json.loads(capsys.readouterr().out)
    types = {r["type"] for r in data}
    assert "join" in types
    assert any(r["inputs"] == "many" for r in data)  # concatRows is variadic


# -- init ---------------------------------------------------------------


def test_init_writes_env_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / ".env"
    cli.main(["init", "--path", str(target)])
    assert target.exists()
    assert "CIAREN_DATABASE_URL" in target.read_text(encoding="utf-8")
    assert "Wrote" in capsys.readouterr().out


def test_init_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("KEEP_ME=1", encoding="utf-8")
    cli.main(["init", "--path", str(target)])
    assert target.read_text(encoding="utf-8") == "KEEP_ME=1"  # untouched


def test_init_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text("KEEP_ME=1", encoding="utf-8")
    cli.main(["init", "--path", str(target), "--force"])
    contents = target.read_text(encoding="utf-8")
    assert "KEEP_ME=1" not in contents
    assert "CIAREN_DATABASE_URL" in contents


# -- serve: API-token exposure warning ---------------------------------


def test_warn_when_exposed_without_token(monkeypatch, capsys):
    monkeypatch.delenv("CIAREN_API_TOKEN", raising=False)
    _clear_settings_cache()
    cli._warn_if_exposed_without_token(argparse.Namespace(host="0.0.0.0"))
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "CIAREN_API_TOKEN" in out


def test_no_warning_on_loopback(monkeypatch, capsys):
    monkeypatch.delenv("CIAREN_API_TOKEN", raising=False)
    _clear_settings_cache()
    cli._warn_if_exposed_without_token(argparse.Namespace(host="127.0.0.1"))
    assert capsys.readouterr().out == ""


def test_no_warning_when_token_set(monkeypatch, capsys):
    monkeypatch.setenv("CIAREN_API_TOKEN", "secret")
    _clear_settings_cache()
    try:
        cli._warn_if_exposed_without_token(argparse.Namespace(host="0.0.0.0"))
        assert capsys.readouterr().out == ""
    finally:
        monkeypatch.delenv("CIAREN_API_TOKEN", raising=False)
        _clear_settings_cache()
