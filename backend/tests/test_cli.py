"""Tests for the `flowframe` CLI entry point.

These exercise argument parsing and env wiring without booting a real server
(uvicorn.run is stubbed).
"""

import argparse

import pytest

from app import cli


def test_serve_defaults() -> None:
    args = cli.build_parser().parse_args(["serve"])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.reload is False
    assert args.no_scheduler is False
    assert args.db_url is None


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
        ]
    )
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.reload is True
    assert args.no_scheduler is True
    assert args.db_url == "sqlite+aiosqlite:///x.db"


def test_apply_serve_env_sets_db_and_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLOWFRAME_DATABASE_URL", raising=False)
    monkeypatch.delenv("FLOWFRAME_SCHEDULER_ENABLED", raising=False)
    args = argparse.Namespace(db_url="postgresql+asyncpg://x", no_scheduler=True)

    cli._apply_serve_env(args)

    import os

    assert os.environ["FLOWFRAME_DATABASE_URL"] == "postgresql+asyncpg://x"
    assert os.environ["FLOWFRAME_SCHEDULER_ENABLED"] == "false"


def test_apply_serve_env_noop_without_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLOWFRAME_DATABASE_URL", raising=False)
    monkeypatch.delenv("FLOWFRAME_SCHEDULER_ENABLED", raising=False)
    args = argparse.Namespace(db_url=None, no_scheduler=False)

    cli._apply_serve_env(args)

    import os

    assert "FLOWFRAME_DATABASE_URL" not in os.environ
    assert "FLOWFRAME_SCHEDULER_ENABLED" not in os.environ


def test_main_serve_invokes_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, **kwargs: object) -> None:
        captured["app_path"] = app_path
        captured.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    cli.main(["serve", "--host", "0.0.0.0", "--port", "9100"])

    assert captured["app_path"] == "app.main:app"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9100
    assert captured["reload"] is False


def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main([])
    out = capsys.readouterr().out
    assert "usage: flowframe" in out
    assert "serve" in out
