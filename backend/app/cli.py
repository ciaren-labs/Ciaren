# SPDX-License-Identifier: AGPL-3.0-only
"""Ciaren command-line entry point.

Exposed as the ``ciaren`` console script (see ``[project.scripts]``), so a
``pip install ciaren`` is followed by a single command to run everything:

    ciaren serve

``serve`` boots the FastAPI app in one process; the app's lifespan starts the
background scheduler, so the API and scheduled runs share that single process —
no broker, no extra services. The ``init`` / ``info`` / ``check`` commands help
first-time setup and troubleshooting, ``db`` manages the schema through Alembic
migrations, and ``transformations`` lists the available node types. Uses only
argparse (stdlib) to keep setup trivial; serve flags are translated to the env
vars the Settings layer reads before the app is imported.

Plugin install/authoring/signing commands live in the separate ``ciaren-plugin``
entry point (see ``cli_plugin.py``) so the everyday ``ciaren`` surface stays
small; ``ciaren plugin ...`` prints a pointer to the new command instead of
failing with an opaque "invalid choice" error.
"""

import argparse
import json
import os
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

_ASYNC_SCHEMES = ("sqlite+aiosqlite", "postgresql+asyncpg", "mysql+aiomysql")

_ENV_TEMPLATE = """\
# Ciaren configuration. Uncomment and edit as needed; every key is optional
# and falls back to the default shown. Values can also be passed as `ciaren
# serve` flags. See `ciaren info` for the currently resolved settings.

# Database (must use an async driver):
#   sqlite+aiosqlite:///./ciaren.db | postgresql+asyncpg://user:pass@host/db
# CIAREN_DATABASE_URL=sqlite+aiosqlite:///./ciaren.db

# Where uploads and run outputs are stored:
# CIAREN_DATA_DIR=.data

# Dataframe engine for runs that don't request one: polars | pandas
# CIAREN_DEFAULT_ENGINE=polars

# How flow compute is offloaded off the event loop: thread | process
# CIAREN_EXECUTION_MODE=thread

# Log output format: auto (color on a TTY, else plain) | text | json
# Use "json" for structured logs when shipping to a log collector.
# CIAREN_LOG_FORMAT=auto

# Background scheduler:
# CIAREN_SCHEDULER_ENABLED=true
# CIAREN_SCHEDULER_POLL_INTERVAL_SECONDS=30
# CIAREN_SCHEDULER_MAX_CONCURRENT_RUNS=1
# CIAREN_SCHEDULER_MAX_CONSECUTIVE_FAILURES=5

# Abandon a run after this many seconds (0 = no limit):
# CIAREN_RUN_TIMEOUT_SECONDS=0

# --- Security -----------------------------------------------------------------
# The API is unauthenticated by default (fine bound to 127.0.0.1). If you expose
# it on a network — e.g. binding 0.0.0.0, like the Docker image — set a token so
# every /api request must send `Authorization: Bearer <token>`. The web UI sends
# it automatically (seed it once via the app URL with `?api_token=<token>`).
# CIAREN_API_TOKEN=

# Pre-shared secret for the POST /api/flows/{id}/trigger webhook (CI/CD, Airflow).
# Unset = the webhook is disabled (404).
# CIAREN_WEBHOOK_SECRET=

# Block connector hosts/endpoints that resolve to internal addresses (loopback,
# link-local incl. cloud metadata, RFC1918). Off by default so local databases
# work; turn on for shared deployments where connection configs aren't trusted.
# CIAREN_CONNECTOR_BLOCK_PRIVATE_HOSTS=false

# Confine the local-folder storage connector to these directories (JSON list).
# Empty = any folder is allowed (default). Set on shared deployments to stop a
# connection from reading/writing arbitrary server files.
# CIAREN_STORAGE_ALLOWED_ROOTS=["/srv/ciaren/data"]

# Strict static checks for the pythonTransform node: reject dangerous imports/
# builtins/dunders at save/run time and run with restricted builtins. Defense in
# depth, not a sandbox. Off by default so existing scripts keep working.
# CIAREN_PYTHON_TRANSFORM_STRICT=false

# --- Machine learning (built in; XGBoost/LightGBM need `pip install ciaren[ml]`) --
# `ciaren init` provisions a default LOCAL MLflow instance below. To use an
# existing MLflow server instead, point MLFLOW_TRACKING_URI at it, e.g.
#   CIAREN_MLFLOW_TRACKING_URI=http://mlflow.internal:5000
# or a database-backed store: sqlite:///./mlflow.db
CIAREN_ML_ENABLED=true
CIAREN_MLFLOW_TRACKING_URI=./mlruns
# Model registry; leave unset to reuse the tracking store:
# CIAREN_MLFLOW_REGISTRY_URI=
# Where trained model artifacts are stored (under DATA_DIR when relative):
# CIAREN_ML_ARTIFACT_DIR=ml_artifacts
"""


def _package_version() -> str:
    try:
        return version("ciaren")
    except PackageNotFoundError:  # pragma: no cover - running from a source checkout
        return "0.0.0"


def _redact_url(url: str) -> str:
    """Hide the password in a connection URL before printing it."""
    return re.sub(r"://([^:/@]+):([^@/]+)@", r"://\1:***@", url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ciaren",
        description="Ciaren - local-first visual data and ML workflow builder.",
    )
    parser.add_argument("--version", action="version", version=f"ciaren {_package_version()}")

    sub = parser.add_subparsers(dest="command")

    # Shared across commands that resolve settings: point at a specific .env file
    # instead of the ./.env picked up by default.
    env_file_parent = argparse.ArgumentParser(add_help=False)
    env_file_parent.add_argument(
        "--env-file",
        default=None,
        metavar="PATH",
        help="Load environment variables from this file before resolving settings.",
    )

    # Shared by read-only commands that can emit machine-readable output.
    output_parent = argparse.ArgumentParser(add_help=False)
    output_parent.add_argument(
        "--output",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table).",
    )

    serve = sub.add_parser(
        "serve",
        help="Run the API server together with the background scheduler.",
        parents=[env_file_parent],
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    serve.add_argument("--port", type=int, default=8055, help="Bind port (default: 8055).")
    serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development only).")
    serve.add_argument(
        "--db-url",
        default=None,
        help="Async database URL; overrides CIAREN_DATABASE_URL.",
    )
    serve.add_argument(
        "--data-dir",
        default=None,
        help="Directory for uploads/outputs; overrides CIAREN_DATA_DIR.",
    )
    serve.add_argument(
        "--engine",
        choices=["polars", "pandas"],
        default=None,
        help="Default dataframe engine; overrides CIAREN_DEFAULT_ENGINE.",
    )
    serve.add_argument(
        "--execution-mode",
        choices=["thread", "process"],
        default=None,
        help="Compute offload mode; overrides CIAREN_EXECUTION_MODE.",
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
    serve.add_argument(
        "--no-demo",
        action="store_true",
        help="Skip seeding the built-in demo project on first boot.",
    )
    serve.add_argument(
        "--run-seed-flows",
        action="store_true",
        help="Run every demo flow once right after first-boot seeding "
        "(populates run history and MLflow). Off by default.",
    )

    init = sub.add_parser("init", help="Write a starter .env config file.")
    init.add_argument("--path", default=".env", help="Where to write the file (default: .env).")
    init.add_argument("--force", action="store_true", help="Overwrite the file if it already exists.")
    init.add_argument("--no-ml", action="store_true", help="Skip provisioning the default local MLflow store.")

    sub.add_parser(
        "info",
        help="Print the resolved configuration the server would use.",
        parents=[env_file_parent, output_parent],
    )
    sub.add_parser(
        "check",
        help="Validate the environment (data dir, database connectivity, engines).",
        parents=[env_file_parent, output_parent],
    )

    db = sub.add_parser("db", help="Manage the database schema (Alembic migrations).")
    db_sub = db.add_subparsers(dest="db_command")
    db_upgrade = db_sub.add_parser(
        "upgrade",
        help="Apply migrations up to the latest revision (safe to re-run).",
        parents=[env_file_parent],
    )
    db_upgrade.add_argument("--revision", default="head", help="Target revision (default: head).")
    db_sub.add_parser(
        "current",
        help="Show the revision the database is currently stamped at.",
        parents=[env_file_parent],
    )
    db_reset = db_sub.add_parser(
        "reset",
        help="DROP all tables and rebuild them from migrations (destructive).",
        parents=[env_file_parent],
    )
    db_reset.add_argument("--yes", action="store_true", help="Confirm the destructive reset (required).")
    db_reset.add_argument(
        "--force",
        action="store_true",
        help="Allow reset even when ENVIRONMENT=production.",
    )

    transformations = sub.add_parser("transformations", help="Inspect the available transformation node types.")
    tf_sub = transformations.add_subparsers(dest="transformations_command")
    tf_sub.add_parser(
        "list",
        help="List every registered transformation node type.",
        parents=[output_parent],
    )

    flow = sub.add_parser("flow", help="Validate and migrate .flow document files.")
    flow_sub = flow.add_subparsers(dest="flow_command")
    flow_validate = flow_sub.add_parser(
        "validate",
        help="Validate a .flow document against the schema and graph structure.",
        parents=[output_parent],
    )
    flow_validate.add_argument("path", help="Path to the .flow / JSON document.")
    flow_migrate = flow_sub.add_parser(
        "migrate",
        help="Migrate a .flow document to a newer schema version.",
        parents=[output_parent],
    )
    flow_migrate.add_argument("path", help="Path to the .flow / JSON document.")
    flow_migrate.add_argument(
        "--to",
        dest="to_version",
        default=None,
        metavar="VERSION",
        help="Target schema version (default: the latest this build supports).",
    )
    flow_migrate.add_argument(
        "--write",
        action="store_true",
        help="Write the migrated document back in place (a .bak backup is kept).",
    )

    return parser


def _load_env_file(args: argparse.Namespace) -> None:
    """Load a user-supplied --env-file into the process environment before any
    settings are resolved. Existing environment variables win (override=False),
    matching pydantic's "env vars > .env" precedence; `serve` flags are applied
    afterwards, so they still take precedence over the file."""
    env_file = getattr(args, "env_file", None)
    if not env_file:
        return
    path = Path(env_file)
    if not path.is_file():
        raise SystemExit(f"--env-file not found: {path}")

    from dotenv import load_dotenv

    load_dotenv(path, override=False)


def _apply_serve_env(args: argparse.Namespace) -> None:
    """Translate serve flags into the env vars the Settings layer reads, before the
    app (and its cached settings) are imported."""
    overrides = {
        "CIAREN_DATABASE_URL": args.db_url,
        "CIAREN_DATA_DIR": args.data_dir,
        "CIAREN_DEFAULT_ENGINE": args.engine,
        "CIAREN_EXECUTION_MODE": args.execution_mode,
    }
    for key, value in overrides.items():
        if value:
            os.environ[key] = value
    if args.no_scheduler:
        os.environ["CIAREN_SCHEDULER_ENABLED"] = "false"
    if getattr(args, "no_demo", False):
        os.environ["CIAREN_SEED_DEMO"] = "false"
    if getattr(args, "run_seed_flows", False):
        os.environ["CIAREN_SEED_RUN_FLOWS"] = "true"


def _serve(args: argparse.Namespace) -> None:
    _load_env_file(args)
    _apply_serve_env(args)

    _print_serve_banner(args)
    _warn_if_exposed_without_token(args)

    import uvicorn

    # Pass the import string (not the app object) so --reload works.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _warn_if_exposed_without_token(args: argparse.Namespace) -> None:
    """Warn when binding to a non-loopback interface without an API token.

    The API is unauthenticated by default and reaches arbitrary code execution
    (pythonTransform, plugin install), so a wide bind with no token is an open
    door. Just a warning — we never refuse to start. See SECURITY.md.
    """
    from app.core.config import get_settings

    if args.host in _LOOPBACK_HOSTS:
        return
    if get_settings().API_TOKEN:
        return
    print(
        f"  WARNING: serving on {args.host} with no API token. The API is "
        "unauthenticated and can execute code (pythonTransform, plugin install).\n"
        "     Set CIAREN_API_TOKEN to require a bearer token, or bind to "
        "127.0.0.1 and use a reverse proxy.\n"
    )


def _print_serve_banner(args: argparse.Namespace) -> None:
    """Tell the user where to actually open the app — the frontend, not the API."""
    from app.core.config import get_settings
    from app.main import frontend_dist_path

    # 0.0.0.0 isn't browsable; show localhost.
    host = "localhost" if args.host in ("0.0.0.0", "::") else args.host
    base = f"http://{host}:{args.port}"
    serves_ui = frontend_dist_path(get_settings()) is not None

    # Use an arrow the console can render, falling back to ASCII on legacy
    # Windows code pages (cp1252) that can't encode "▶".
    arrow = "▶"
    enc = getattr(sys.stdout, "encoding", None) or ""
    try:
        arrow.encode(enc or "ascii")
    except (UnicodeEncodeError, LookupError):
        arrow = ">"

    print("\n  Ciaren")
    if serves_ui:
        print(f"  {arrow} Open the app:  {base}")
        print(f"    API + docs:    {base}/docs")
    else:
        print(f"  {arrow} API:           {base}  (docs at {base}/docs)")
        print("    Web UI:        run `npm run dev` in frontend/, then open http://localhost:5173")
        print("                   (or build it with `npm run build` to serve the UI from here)")
    print("")


def _info(args: argparse.Namespace) -> None:
    _load_env_file(args)
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
        # Booleans only — never print the secret values themselves.
        "api_token_set": s.API_TOKEN is not None,
        "webhook_secret_set": s.WEBHOOK_SECRET is not None,
        "connector_block_private_hosts": s.CONNECTOR_BLOCK_PRIVATE_HOSTS,
        "python_transform_strict": s.PYTHON_TRANSFORM_STRICT,
        "ml_enabled": s.ML_ENABLED,
        "mlflow_tracking_uri": s.MLFLOW_TRACKING_URI,
        "ml_artifact_dir": s.ml_artifact_path,
    }
    if getattr(args, "output", "table") == "json":
        print(json.dumps(rows, indent=2))
        return
    width = max(len(k) for k in rows)
    print("Ciaren resolved configuration:")
    for key, value in rows.items():
        print(f"  {key.ljust(width)}  {value}")


def _check(args: argparse.Namespace) -> None:
    _load_env_file(args)
    from app.core.config import get_settings
    from app.engine.backends import available_engines

    s = get_settings()
    checks: list[dict[str, str]] = []

    # Data dir writable?
    data_dir = Path(s.DATA_DIR)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".ciaren-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append({"name": "data_dir", "status": "ok", "detail": str(data_dir.resolve())})
    except OSError as exc:
        checks.append({"name": "data_dir", "status": "fail", "detail": str(exc)})

    # Async driver?
    if any(s.DATABASE_URL.startswith(scheme) for scheme in _ASYNC_SCHEMES):
        checks.append({"name": "async_driver", "status": "ok", "detail": _redact_url(s.DATABASE_URL)})
    else:
        checks.append(
            {
                "name": "async_driver",
                "status": "warn",
                "detail": f"{_redact_url(s.DATABASE_URL)} (expected one of {', '.join(_ASYNC_SCHEMES)})",
            }
        )

    # Database reachable?
    try:
        _probe_database(s.DATABASE_URL)
        checks.append({"name": "database", "status": "ok", "detail": "reachable"})
    except Exception as exc:  # noqa: BLE001 - report any connection failure
        checks.append({"name": "database", "status": "fail", "detail": str(exc)})

    checks.append({"name": "engines", "status": "ok", "detail": ", ".join(available_engines())})

    # ML: scikit-learn/MLflow/joblib are core deps, so this only warns on a
    # broken or stripped-down install (e.g. installed with --no-deps).
    if s.ML_ENABLED:
        from app.ml.availability import ml_core_available

        if ml_core_available():
            checks.append({"name": "ml", "status": "ok", "detail": f"enabled, tracking={s.MLFLOW_TRACKING_URI}"})
        else:
            checks.append(
                {
                    "name": "ml",
                    "status": "warn",
                    "detail": (
                        "ML_ENABLED but scikit-learn/mlflow/joblib not importable — "
                        "reinstall with `pip install --force-reinstall ciaren` (these are core dependencies)"
                    ),
                }
            )
    else:
        checks.append({"name": "ml", "status": "ok", "detail": "disabled"})

    ok = all(c["status"] != "fail" for c in checks)

    if getattr(args, "output", "table") == "json":
        print(json.dumps({"ok": ok, "checks": checks}, indent=2))
        if not ok:
            raise SystemExit(1)
        return

    labels = {"ok": "[ok]  ", "warn": "[warn]", "fail": "[FAIL]"}
    for c in checks:
        print(f"{labels[c['status']]} {c['name']}: {c['detail']}")
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


_DEFAULT_MLFLOW_DIR = "mlruns"


def _init(args: argparse.Namespace) -> None:
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"{path} already exists — use --force to overwrite.")
        return
    path.write_text(_ENV_TEMPLATE, encoding="utf-8")
    print(f"Wrote {path}. Edit it, then run `ciaren serve`.")

    # Provision a default local MLflow instance so ML flows work out of the box.
    # This is just a directory the local MLflow file store writes into; pointing
    # CIAREN_MLFLOW_TRACKING_URI at an existing server overrides it entirely.
    if not getattr(args, "no_ml", False):
        mlruns = Path(_DEFAULT_MLFLOW_DIR)
        try:
            mlruns.mkdir(parents=True, exist_ok=True)
            print(
                f"Provisioned a local MLflow store at {mlruns.resolve()} "
                f"(override with CIAREN_MLFLOW_TRACKING_URI to use an existing MLflow)."
            )
        except OSError as exc:  # pragma: no cover - unusual fs error
            print(f"Could not create {mlruns}: {exc}")


def _db(args: argparse.Namespace) -> None:
    _load_env_file(args)
    from app.core.config import get_settings
    from app.db import migrations

    command = getattr(args, "db_command", None)
    if command == "upgrade":
        adopted = migrations.upgrade(args.revision)
        if adopted:
            print("Existing schema detected without migration history — adopted it (stamped current revision).")
        print(f"Database is up to date ({args.revision}).")
    elif command == "current":
        migrations.current()
    elif command == "reset":
        if get_settings().ENVIRONMENT == "production" and not args.force:
            raise SystemExit(
                "Refusing to reset the database while ENVIRONMENT=production. Pass --force if you really mean it."
            )
        if not args.yes:
            raise SystemExit("`db reset` drops every table. Re-run with --yes to confirm.")
        migrations.reset()
        print("Database reset: all tables dropped and rebuilt from migrations.")
    else:
        print("usage: ciaren db {upgrade,current,reset}")


def _transformations(args: argparse.Namespace) -> None:
    if getattr(args, "transformations_command", None) != "list":
        print("usage: ciaren transformations list")
        return
    from app.engine.registry import get_transformation, list_transformation_types

    rows: list[dict[str, Any]] = []
    for type_name in list_transformation_types():
        t = get_transformation(type_name)
        rows.append(
            {
                "type": type_name,
                "inputs": "many" if t.multi_input else str(len(t.input_handles)),
                "input_handles": list(t.input_handles),
            }
        )

    if getattr(args, "output", "table") == "json":
        print(json.dumps(rows, indent=2))
        return

    width = max(len(r["type"]) for r in rows)
    print(f"{len(rows)} transformation node types:")
    for r in rows:
        print(f"  {r['type'].ljust(width)}  inputs={r['inputs']}")


def _flow(args: argparse.Namespace) -> None:
    from app.flow_schema import (
        CURRENT_SCHEMA_VERSION,
        FlowSchemaError,
        MigrationError,
        migrate,
        validate,
    )

    command = getattr(args, "flow_command", None)
    if command not in ("validate", "migrate"):
        print("usage: ciaren flow {validate,migrate}")
        return

    path = Path(args.path)
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"could not read {path}: {exc}") from exc

    if command == "validate":
        try:
            document = validate(data)
        except FlowSchemaError as exc:
            if getattr(args, "output", "table") == "json":
                print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
            else:
                print(f"INVALID: {exc}")
            raise SystemExit(1) from exc
        if getattr(args, "output", "table") == "json":
            print(json.dumps({"valid": True, "schemaVersion": document.schema_version}, indent=2))
        else:
            print(f"OK: valid .flow document (schemaVersion={document.schema_version})")
        return

    # migrate
    target = getattr(args, "to_version", None) or CURRENT_SCHEMA_VERSION
    try:
        migrated = migrate(data, target=target)
    except MigrationError as exc:
        raise SystemExit(f"migration failed: {exc}") from exc

    if getattr(args, "write", False):
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(migrated, indent=2), encoding="utf-8")
        print(f"Migrated {path} to schemaVersion={target} (backup: {backup.name}).")
    else:
        print(json.dumps(migrated, indent=2))


def main(argv: list[str] | None = None) -> None:
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0] == "plugin":
        rest = " ".join(raw[1:])
        print("`ciaren plugin` has moved to its own command: `ciaren-plugin`.")
        print(f"Run `ciaren-plugin {rest}`." if rest else "Run `ciaren-plugin --help` to see available commands.")
        raise SystemExit(1)

    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "serve": _serve,
        "init": _init,
        "info": _info,
        "check": _check,
        "db": _db,
        "transformations": _transformations,
        "flow": _flow,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return
    handler(args)


if __name__ == "__main__":  # pragma: no cover
    main()
