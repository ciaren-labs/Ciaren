"""FlowFrame command-line entry point.

Exposed as the ``flowframe`` console script (see ``[project.scripts]``), so a
``pip install flowframe`` is followed by a single command to run everything:

    flowframe serve

``serve`` boots the FastAPI app in one process; the app's lifespan starts the
background scheduler, so the API and scheduled runs share that single process —
no broker, no extra services. The ``init`` / ``info`` / ``check`` commands help
first-time setup and troubleshooting. Uses only argparse (stdlib) to keep setup
trivial; serve flags are translated to the env vars the Settings layer reads
before the app is imported.
"""

import argparse
import os
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_ASYNC_SCHEMES = ("sqlite+aiosqlite", "postgresql+asyncpg", "mysql+aiomysql")

_ENV_TEMPLATE = """\
# FlowFrame configuration. Uncomment and edit as needed; every key is optional
# and falls back to the default shown. Values can also be passed as `flowframe
# serve` flags. See `flowframe info` for the currently resolved settings.

# Database (must use an async driver):
#   sqlite+aiosqlite:///./flowframe.db | postgresql+asyncpg://user:pass@host/db
# FLOWFRAME_DATABASE_URL=sqlite+aiosqlite:///./flowframe.db

# Where uploads and run outputs are stored:
# FLOWFRAME_DATA_DIR=.data

# Dataframe engine for runs that don't request one: polars | pandas
# FLOWFRAME_DEFAULT_ENGINE=polars

# How flow compute is offloaded off the event loop: thread | process
# FLOWFRAME_EXECUTION_MODE=thread

# Background scheduler:
# FLOWFRAME_SCHEDULER_ENABLED=true
# FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS=30
# FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS=1
# FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES=5

# Abandon a run after this many seconds (0 = no limit):
# FLOWFRAME_RUN_TIMEOUT_SECONDS=0
"""


def _package_version() -> str:
    try:
        return version("flowframe")
    except PackageNotFoundError:  # pragma: no cover - running from a source checkout
        return "0.0.0"


def _redact_url(url: str) -> str:
    """Hide the password in a connection URL before printing it."""
    return re.sub(r"://([^:/@]+):([^@/]+)@", r"://\1:***@", url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flowframe",
        description="FlowFrame — local-first visual ETL builder.",
    )
    parser.add_argument(
        "--version", action="version", version=f"flowframe {_package_version()}"
    )

    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser(
        "serve", help="Run the API server together with the background scheduler."
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    serve.add_argument(
        "--reload", action="store_true", help="Auto-reload on code changes (development only)."
    )
    serve.add_argument(
        "--db-url",
        default=None,
        help="Async database URL; overrides FLOWFRAME_DATABASE_URL.",
    )
    serve.add_argument(
        "--data-dir",
        default=None,
        help="Directory for uploads/outputs; overrides FLOWFRAME_DATA_DIR.",
    )
    serve.add_argument(
        "--engine",
        choices=["polars", "pandas"],
        default=None,
        help="Default dataframe engine; overrides FLOWFRAME_DEFAULT_ENGINE.",
    )
    serve.add_argument(
        "--execution-mode",
        choices=["thread", "process"],
        default=None,
        help="Compute offload mode; overrides FLOWFRAME_EXECUTION_MODE.",
    )
    serve.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default=None,
        help="uvicorn log level.",
    )
    serve.add_argument(
        "--no-scheduler",
        action="store_true",
        help="Start the API without the background scheduler.",
    )

    init = sub.add_parser("init", help="Write a starter .env config file.")
    init.add_argument("--path", default=".env", help="Where to write the file (default: .env).")
    init.add_argument(
        "--force", action="store_true", help="Overwrite the file if it already exists."
    )

    sub.add_parser("info", help="Print the resolved configuration the server would use.")
    sub.add_parser(
        "check", help="Validate the environment (data dir, database connectivity, engines)."
    )
    return parser


def _apply_serve_env(args: argparse.Namespace) -> None:
    """Translate serve flags into the env vars the Settings layer reads, before the
    app (and its cached settings) are imported."""
    overrides = {
        "FLOWFRAME_DATABASE_URL": args.db_url,
        "FLOWFRAME_DATA_DIR": args.data_dir,
        "FLOWFRAME_DEFAULT_ENGINE": args.engine,
        "FLOWFRAME_EXECUTION_MODE": args.execution_mode,
    }
    for key, value in overrides.items():
        if value:
            os.environ[key] = value
    if args.no_scheduler:
        os.environ["FLOWFRAME_SCHEDULER_ENABLED"] = "false"


def _serve(args: argparse.Namespace) -> None:
    _apply_serve_env(args)
    import uvicorn

    # Pass the import string (not the app object) so --reload works.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


def _info(args: argparse.Namespace) -> None:
    from app.core.config import get_settings

    s = get_settings()
    rows = {
        "app_name": s.APP_NAME,
        "environment": s.ENVIRONMENT,
        "database_url": _redact_url(s.DATABASE_URL),
        "data_dir": str(Path(s.DATA_DIR).resolve()),
        "default_engine": s.DEFAULT_ENGINE,
        "execution_mode": s.EXECUTION_MODE,
        "scheduler_enabled": s.SCHEDULER_ENABLED,
        "scheduler_poll_seconds": s.SCHEDULER_POLL_INTERVAL_SECONDS,
        "scheduler_max_concurrent_runs": s.SCHEDULER_MAX_CONCURRENT_RUNS,
        "scheduler_max_consecutive_failures": s.SCHEDULER_MAX_CONSECUTIVE_FAILURES,
        "run_timeout_seconds": s.RUN_TIMEOUT_SECONDS,
        "max_upload_size_mb": s.MAX_UPLOAD_SIZE_MB,
    }
    width = max(len(k) for k in rows)
    print("FlowFrame resolved configuration:")
    for key, value in rows.items():
        print(f"  {key.ljust(width)}  {value}")


def _check(args: argparse.Namespace) -> None:
    from app.core.config import get_settings
    from app.engine.backends import available_engines

    s = get_settings()
    ok = True

    # Data dir writable?
    data_dir = Path(s.DATA_DIR)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".flowframe-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"[ok]   data dir writable: {data_dir.resolve()}")
    except OSError as exc:
        ok = False
        print(f"[FAIL] data dir not writable: {data_dir} ({exc})")

    # Async driver?
    if any(s.DATABASE_URL.startswith(scheme) for scheme in _ASYNC_SCHEMES):
        print(f"[ok]   database driver is async: {_redact_url(s.DATABASE_URL)}")
    else:
        print(
            f"[warn] database URL may not use an async driver: {_redact_url(s.DATABASE_URL)} "
            f"(expected one of {', '.join(_ASYNC_SCHEMES)})"
        )

    # Database reachable?
    try:
        _probe_database(s.DATABASE_URL)
        print("[ok]   database reachable")
    except Exception as exc:  # noqa: BLE001 - report any connection failure
        ok = False
        print(f"[FAIL] database unreachable: {exc}")

    print(f"[ok]   engines available: {', '.join(available_engines())}")

    if not ok:
        print("\nSome checks failed.")
        raise SystemExit(1)
    print("\nAll checks passed.")


def _probe_database(url: str) -> None:
    """Open a throwaway connection and run a trivial query. Uses a fresh engine
    (not the app's) so it honours the current settings without side effects."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _run() -> None:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    asyncio.run(_run())


def _init(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"{path} already exists — use --force to overwrite.")
        return
    path.write_text(_ENV_TEMPLATE, encoding="utf-8")
    print(f"Wrote {path}. Edit it, then run `flowframe serve`.")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"serve": _serve, "init": _init, "info": _info, "check": _check}
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return
    handler(args)


if __name__ == "__main__":  # pragma: no cover
    main()
