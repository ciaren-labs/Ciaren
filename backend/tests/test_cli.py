"""Tests for the `flowframe` CLI entry point.

These exercise argument parsing, env wiring, and the helper commands without
booting a real server (uvicorn.run is stubbed) or mutating real config/DB files.
"""

import argparse
import os
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
    assert args.port == 8000
    assert args.reload is False
    assert args.no_scheduler is False
    assert args.db_url is None
    assert args.data_dir is None
    assert args.engine is None
    assert args.execution_mode is None
    assert args.log_level is None


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
            "/tmp/ff",
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
    assert args.data_dir == "/tmp/ff"
    assert args.engine == "pandas"
    assert args.execution_mode == "process"
    assert args.log_level == "debug"


def test_engine_choice_is_validated() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["serve", "--engine", "spark"])


def test_apply_serve_env_sets_all_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "FLOWFRAME_DATABASE_URL",
        "FLOWFRAME_DATA_DIR",
        "FLOWFRAME_DEFAULT_ENGINE",
        "FLOWFRAME_EXECUTION_MODE",
        "FLOWFRAME_SCHEDULER_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    args = argparse.Namespace(
        db_url="postgresql+asyncpg://x",
        data_dir="/data/ff",
        engine="pandas",
        execution_mode="process",
        no_scheduler=True,
    )

    cli._apply_serve_env(args)

    assert os.environ["FLOWFRAME_DATABASE_URL"] == "postgresql+asyncpg://x"
    assert os.environ["FLOWFRAME_DATA_DIR"] == "/data/ff"
    assert os.environ["FLOWFRAME_DEFAULT_ENGINE"] == "pandas"
    assert os.environ["FLOWFRAME_EXECUTION_MODE"] == "process"
    assert os.environ["FLOWFRAME_SCHEDULER_ENABLED"] == "false"


def test_apply_serve_env_noop_without_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLOWFRAME_DATABASE_URL", raising=False)
    monkeypatch.delenv("FLOWFRAME_SCHEDULER_ENABLED", raising=False)
    args = argparse.Namespace(
        db_url=None, data_dir=None, engine=None, execution_mode=None, no_scheduler=False
    )

    cli._apply_serve_env(args)

    assert "FLOWFRAME_DATABASE_URL" not in os.environ
    assert "FLOWFRAME_SCHEDULER_ENABLED" not in os.environ


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
    assert "usage: flowframe" in out
    assert "serve" in out


# -- info ---------------------------------------------------------------


def test_info_prints_and_redacts_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FLOWFRAME_DATABASE_URL", "postgresql+asyncpg://user:s3cret@host/db")
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


# -- check --------------------------------------------------------------


def test_check_passes_with_reachable_db(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FLOWFRAME_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))
    _clear_settings_cache()
    try:
        cli.main(["check"])  # must not raise
    finally:
        _clear_settings_cache()
    out = capsys.readouterr().out
    assert "All checks passed" in out
    assert "[FAIL]" not in out


def test_check_fails_when_db_unreachable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FLOWFRAME_DATA_DIR", str(tmp_path))

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
    assert "[FAIL] database unreachable" in capsys.readouterr().out


# -- init ---------------------------------------------------------------


def test_init_writes_env_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target = tmp_path / ".env"
    cli.main(["init", "--path", str(target)])
    assert target.exists()
    assert "FLOWFRAME_DATABASE_URL" in target.read_text(encoding="utf-8")
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
    assert "FLOWFRAME_DATABASE_URL" in contents
