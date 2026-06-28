"""FlowFrame command-line entry point.

Exposed as the ``flowframe`` console script (see ``[project.scripts]``), so a
``pip install flowframe`` is followed by a single command to run everything:

    flowframe serve

``serve`` boots the FastAPI app in one process; the app's lifespan starts the
background scheduler, so the API and scheduled runs share that single process —
no broker, no extra services. The ``init`` / ``info`` / ``check`` commands help
first-time setup and troubleshooting, ``db`` manages the schema through Alembic
migrations, and ``transformations`` lists the available node types. Uses only
argparse (stdlib) to keep setup trivial; serve flags are translated to the env
vars the Settings layer reads before the app is imported.
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

# Log output format: auto (color on a TTY, else plain) | text | json
# Use "json" for structured logs when shipping to a log collector.
# FLOWFRAME_LOG_FORMAT=auto

# Background scheduler:
# FLOWFRAME_SCHEDULER_ENABLED=true
# FLOWFRAME_SCHEDULER_POLL_INTERVAL_SECONDS=30
# FLOWFRAME_SCHEDULER_MAX_CONCURRENT_RUNS=1
# FLOWFRAME_SCHEDULER_MAX_CONSECUTIVE_FAILURES=5

# Abandon a run after this many seconds (0 = no limit):
# FLOWFRAME_RUN_TIMEOUT_SECONDS=0

# --- Machine learning (optional; requires `pip install flowframe[ml]`) --------
# `flowframe init` provisions a default LOCAL MLflow instance below. To use an
# existing MLflow server instead, point MLFLOW_TRACKING_URI at it, e.g.
#   FLOWFRAME_MLFLOW_TRACKING_URI=http://mlflow.internal:5000
# or a database-backed store: sqlite:///./mlflow.db
FLOWFRAME_ML_ENABLED=true
FLOWFRAME_MLFLOW_TRACKING_URI=./mlruns
# Model registry; leave unset to reuse the tracking store:
# FLOWFRAME_MLFLOW_REGISTRY_URI=
# Where trained model artifacts are stored (under DATA_DIR when relative):
# FLOWFRAME_ML_ARTIFACT_DIR=ml_artifacts
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
    parser.add_argument("--version", action="version", version=f"flowframe {_package_version()}")

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

    plugin = sub.add_parser("plugin", help="Install, inspect, and sign FlowFrame plugins.")
    plugin_sub = plugin.add_subparsers(dest="plugin_command")

    plugin_sub.add_parser("list", help="List discovered plugins and their status.", parents=[output_parent])

    p_install = plugin_sub.add_parser("install", help="Install a .ffplugin package (or a source dir with --dir).")
    p_install.add_argument("path", help="Path to the .ffplugin file (or plugin source directory with --dir).")
    p_install.add_argument("--dir", action="store_true", help="Install from an unpacked source directory.")
    p_install.add_argument("--trusted", action="store_true", help="Refuse unless signed by a trusted key.")
    p_install.add_argument("--force", action="store_true", help="Overwrite an existing install.")

    p_uninstall = plugin_sub.add_parser("uninstall", help="Remove an installed plugin by id.")
    p_uninstall.add_argument("plugin_id", help="The plugin id to remove.")

    p_verify = plugin_sub.add_parser(
        "verify", help="Verify a .ffplugin's signature and integrity.", parents=[output_parent]
    )
    p_verify.add_argument("path", help="Path to the .ffplugin file.")

    p_enable = plugin_sub.add_parser("enable", help="Enable a plugin.")
    p_enable.add_argument("plugin_id")
    p_disable = plugin_sub.add_parser("disable", help="Disable a plugin (its code won't load).")
    p_disable.add_argument("plugin_id")

    plugin_sub.add_parser("keygen", help="Generate an Ed25519 signing keypair (for publishers).")

    p_pack = plugin_sub.add_parser("pack", help="Package a plugin source directory into an (unsigned) .ffplugin.")
    p_pack.add_argument("src_dir", help="Plugin source directory (contains flowframe-plugin.json).")
    p_pack.add_argument("out", help="Output .ffplugin path.")
    p_pack.add_argument(
        "--compile",
        action="store_true",
        dest="compile_python",
        help="Ship compiled .pyc bytecode instead of .py source (deters casual "
        "inspection of paid plugins; locks the package to this Python version).",
    )

    p_sign = plugin_sub.add_parser("sign", help="Sign a .ffplugin in place with an Ed25519 private key.")
    p_sign.add_argument("path", help="Path to the .ffplugin file.")
    p_sign.add_argument("--key", required=True, help="Hex-encoded Ed25519 private key.")
    p_sign.add_argument(
        "--key-id", required=True, dest="key_id", help="Identifier clients use to look up the public key."
    )
    p_sign.add_argument("--publisher", default="", help="Publisher name to embed in the signature.")

    p_search = plugin_sub.add_parser("search", help="Search a local marketplace index.", parents=[output_parent])
    p_search.add_argument("query", nargs="?", default="", help="Search text (empty lists all).")
    p_search.add_argument("--index", required=True, help="Path to a marketplace index JSON file.")

    p_index = plugin_sub.add_parser("index", help="Author a local marketplace index (the 'Explore' catalog).")
    index_sub = p_index.add_subparsers(dest="index_command")
    p_index_add = index_sub.add_parser("add", help="Add/replace a plugin entry in a marketplace index.")
    p_index_add.add_argument("package", help="Path to the .ffplugin to add.")
    p_index_add.add_argument("--index", required=True, help="Marketplace index JSON file (created if absent).")
    p_index_add.add_argument(
        "--download-url",
        default=None,
        dest="download_url",
        help="Where clients fetch the artifact. Defaults to the package path relative to the index file.",
    )

    p_license = plugin_sub.add_parser("license", help="Issue, import, and inspect plugin license tokens.")
    license_sub = p_license.add_subparsers(dest="license_command")
    p_lic_issue = license_sub.add_parser("issue", help="Sign a license token (publisher).")
    p_lic_issue.add_argument("--key", required=True, help="Hex-encoded Ed25519 private key.")
    p_lic_issue.add_argument("--user", required=True, dest="user_id", help="Licensed user id.")
    p_lic_issue.add_argument("--plugin", required=True, dest="plugin_id", help="Plugin id the token grants.")
    p_lic_issue.add_argument("--type", default="pro", dest="license_type", help="License type (default: pro).")
    p_lic_issue.add_argument("--expires", required=True, help="Expiry, ISO-8601 (e.g. 2027-01-01T00:00:00Z).")
    p_lic_issue.add_argument("--grace", required=True, help="Offline grace end, ISO-8601.")
    p_lic_issue.add_argument("--out", default=None, help="Write the token JSON here (default: stdout).")
    p_lic_import = license_sub.add_parser("import", help="Cache a license token locally (user).")
    p_lic_import.add_argument("path", help="Path to the token JSON file.")
    p_lic_status = license_sub.add_parser("status", help="Show a cached license token's status.")
    p_lic_status.add_argument("plugin_id", help="Plugin id to inspect.")
    p_lic_status.add_argument("--key", default=None, help="Issuer public key (hex) to verify the signature.")

    p_lic = plugin_sub.add_parser(
        "licenses", help="Scan installed dependency licenses for redistribution review.", parents=[output_parent]
    )
    p_lic.add_argument("--flagged-only", action="store_true", help="Only show packages that need review.")
    p_lic.add_argument("--fail-on-flagged", action="store_true", help="Exit non-zero if any package is flagged.")

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
    if getattr(args, "no_demo", False):
        os.environ["FLOWFRAME_SEED_DEMO"] = "false"
    if getattr(args, "run_seed_flows", False):
        os.environ["FLOWFRAME_SEED_RUN_FLOWS"] = "true"


def _serve(args: argparse.Namespace) -> None:
    _load_env_file(args)
    _apply_serve_env(args)

    _print_serve_banner(args)

    import uvicorn

    # Pass the import string (not the app object) so --reload works.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
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

    print("\n  FlowFrame")
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
        "ml_enabled": s.ML_ENABLED,
        "mlflow_tracking_uri": s.MLFLOW_TRACKING_URI,
        "ml_artifact_dir": s.ml_artifact_path,
    }
    if getattr(args, "output", "table") == "json":
        print(json.dumps(rows, indent=2))
        return
    width = max(len(k) for k in rows)
    print("FlowFrame resolved configuration:")
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
        probe = data_dir / ".flowframe-write-test"
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

    # ML extension: report whether the feature is enabled and its libraries present.
    if s.ML_ENABLED:
        from app.ml.availability import ml_core_available

        if ml_core_available():
            checks.append({"name": "ml", "status": "ok", "detail": f"enabled, tracking={s.MLFLOW_TRACKING_URI}"})
        else:
            checks.append(
                {
                    "name": "ml",
                    "status": "warn",
                    "detail": "ML_ENABLED but [ml] extra not installed — pip install flowframe[ml]",
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
    print(f"Wrote {path}. Edit it, then run `flowframe serve`.")

    # Provision a default local MLflow instance so ML flows work out of the box.
    # This is just a directory the local MLflow file store writes into; pointing
    # FLOWFRAME_MLFLOW_TRACKING_URI at an existing server overrides it entirely.
    if not getattr(args, "no_ml", False):
        mlruns = Path(_DEFAULT_MLFLOW_DIR)
        try:
            mlruns.mkdir(parents=True, exist_ok=True)
            print(
                f"Provisioned a local MLflow store at {mlruns.resolve()} "
                f"(override with FLOWFRAME_MLFLOW_TRACKING_URI to use an existing MLflow)."
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
        print("usage: flowframe db {upgrade,current,reset}")


def _transformations(args: argparse.Namespace) -> None:
    if getattr(args, "transformations_command", None) != "list":
        print("usage: flowframe transformations list")
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
        print("usage: flowframe flow {validate,migrate}")
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


def _plugin(args: argparse.Namespace) -> None:
    command = getattr(args, "plugin_command", None)
    if command == "list":
        _plugin_list(args)
    elif command == "install":
        _plugin_install(args)
    elif command == "uninstall":
        _plugin_uninstall(args)
    elif command == "verify":
        _plugin_verify(args)
    elif command in ("enable", "disable"):
        _plugin_toggle(args, enable=command == "enable")
    elif command == "keygen":
        _plugin_keygen()
    elif command == "pack":
        _plugin_pack(args)
    elif command == "sign":
        _plugin_sign(args)
    elif command == "search":
        _plugin_search(args)
    elif command == "index":
        _plugin_index(args)
    elif command == "license":
        _plugin_license(args)
    elif command == "licenses":
        _plugin_licenses(args)
    else:
        print(
            "usage: flowframe plugin "
            "{list,install,uninstall,verify,enable,disable,keygen,pack,sign,search,index,license,licenses}"
        )


def _plugin_list(args: argparse.Namespace) -> None:
    from app.plugins import get_load_result, get_plugin_state

    result = get_load_result()
    state = get_plugin_state()
    rows: list[dict[str, Any]] = []
    for p in result.loaded:
        rows.append({"id": p.metadata.id, "name": p.metadata.name, "status": "loaded", "source": p.source})
    for g in result.gated:
        rows.append({"id": g.plugin_id, "name": g.name, "status": g.reason, "source": g.source})
    errors = [{"source": e.source, "error": e.error} for e in result.errors]

    if getattr(args, "output", "table") == "json":
        print(json.dumps({"plugins": rows, "errors": errors}, indent=2))
        return
    if not rows and not errors:
        print("No external plugins discovered.")
        return
    for r in rows:
        print(f"  [{r['status']:<17}] {r['id']:<24} {r['name']}  ({r['source']})")
    for e in errors:
        print(f"  [error            ] {e['source']}: {e['error']}")
    _ = state  # reserved for showing granted permissions in a future column


def _plugin_install(args: argparse.Namespace) -> None:
    from app.plugins.install import InstallError, install_directory, install_ffplugin
    from app.plugins.package import PackageError

    try:
        if args.dir:
            res = install_directory(args.path, force=args.force)
        else:
            res = install_ffplugin(args.path, require_trusted=args.trusted, force=args.force)
    except (InstallError, PackageError) as exc:
        raise SystemExit(f"install failed: {exc}") from exc
    v = res.verification
    # Persist how it verified so the app can show a trust badge later.
    from app.plugins import get_plugin_state

    state = get_plugin_state()
    state.set_signature(res.plugin_id, v.outcome)
    state.save()
    print(f"Installed {res.plugin_id} -> {res.location}")
    print(f"  signature: {v.outcome} ({v.reason})")
    print("Run `flowframe serve` (or restart) to load it.")


def _plugin_uninstall(args: argparse.Namespace) -> None:
    from app.plugins.install import uninstall_plugin

    removed = uninstall_plugin(args.plugin_id)
    print(f"Uninstalled {args.plugin_id}." if removed else f"{args.plugin_id} is not installed.")


def _plugin_verify(args: argparse.Namespace) -> None:
    from app.plugins.package import PackageError, read_manifest, verify_package

    try:
        manifest = read_manifest(args.path)
        result = verify_package(args.path)
    except PackageError as exc:
        raise SystemExit(f"verify failed: {exc}") from exc
    if getattr(args, "output", "table") == "json":
        print(
            json.dumps(
                {
                    "id": manifest.id,
                    "outcome": result.outcome,
                    "signed": result.signed,
                    "digest": result.digest,
                    "reason": result.reason,
                    "publisher": result.publisher,
                },
                indent=2,
            )
        )
    else:
        print(f"Plugin:    {manifest.id} ({manifest.name} {manifest.version})")
        print(f"Digest:    {result.digest}")
        print(f"Signature: {result.outcome} — {result.reason}")
    if result.outcome == "invalid":
        raise SystemExit(1)


def _plugin_toggle(args: argparse.Namespace, *, enable: bool) -> None:
    from app.plugins import get_plugin_state

    state = get_plugin_state()
    state.set_enabled(args.plugin_id, enable)
    state.save()
    print(f"{'Enabled' if enable else 'Disabled'} {args.plugin_id}. Restart `flowframe serve` to apply.")


def _plugin_keygen() -> None:
    from app.plugin_api.signing import SigningUnavailableError, generate_keypair

    try:
        private_hex, public_hex = generate_keypair()
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    print("Ed25519 keypair generated. Keep the private key secret.\n")
    print(f"  private_key: {private_hex}")
    print(f"  public_key:  {public_hex}")
    print("\nPublish the public key as a trusted key, e.g.:")
    print(f'  FLOWFRAME_TRUSTED_PLUGIN_KEYS=\'{{"your-key-id": "{public_hex}"}}\'')


def _plugin_pack(args: argparse.Namespace) -> None:
    from app.plugins.package import PackageError, pack_directory

    try:
        out = pack_directory(args.src_dir, args.out, compile_python=getattr(args, "compile_python", False))
    except PackageError as exc:
        raise SystemExit(f"pack failed: {exc}") from exc
    note = " (compiled bytecode)" if getattr(args, "compile_python", False) else ""
    print(f"Wrote {out} (unsigned{note}). Sign it with `flowframe plugin sign`.")
    if getattr(args, "compile_python", False):
        print(f"  Built for Python {sys.version_info.major}.{sys.version_info.minor}; rebuild per Python version.")


def _plugin_sign(args: argparse.Namespace) -> None:
    from app.plugin_api.signing import SigningUnavailableError
    from app.plugins.package import PackageError, sign_package

    try:
        sig = sign_package(args.path, args.key, key_id=args.key_id, publisher=args.publisher)
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    except PackageError as exc:
        raise SystemExit(f"sign failed: {exc}") from exc
    print(f"Signed {args.path}")
    print(f"  key_id: {sig.key_id}")
    print(f"  digest: {sig.digest}")


def _plugin_index(args: argparse.Namespace) -> None:
    if getattr(args, "index_command", None) != "add":
        print("usage: flowframe plugin index add <package.ffplugin> --index <index.json>")
        return
    from app.plugins.marketplace import add_to_index_file
    from app.plugins.package import PackageError

    try:
        entry = add_to_index_file(args.index, args.package, download_url=args.download_url)
    except (OSError, ValueError, PackageError) as exc:
        raise SystemExit(f"index add failed: {exc}") from exc
    print(f"Added {entry.id} {entry.version} to {args.index}")
    print(f"  downloadUrl: {entry.download_url}")
    print(f"  digest:      {entry.digest}")
    if entry.key_id:
        print(f"  keyId:       {entry.key_id}")


def _plugin_search(args: argparse.Namespace) -> None:
    from app.plugins.marketplace import load_index

    try:
        index = load_index(args.index)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not read index: {exc}") from exc
    matches = index.search(args.query)
    if getattr(args, "output", "table") == "json":
        print(json.dumps([m.model_dump(by_alias=True) for m in matches], indent=2))
        return
    if not matches:
        print("No matching plugins.")
        return
    for m in matches:
        flag = " [license]" if m.license_required else ""
        print(f"  {m.id:<24} {m.version:<8} {m.name}{flag}")
        if m.description:
            print(f"      {m.description}")


def _plugin_license(args: argparse.Namespace) -> None:
    command = getattr(args, "license_command", None)
    if command == "issue":
        _plugin_license_issue(args)
    elif command == "import":
        _plugin_license_import(args)
    elif command == "status":
        _plugin_license_status(args)
    else:
        print("usage: flowframe plugin license {issue,import,status}")


def _plugin_license_issue(args: argparse.Namespace) -> None:
    from app.plugin_api.signing import SigningUnavailableError, sign
    from app.plugins.licensing import LicenseToken

    token = LicenseToken(
        user_id=args.user_id,
        plugin_id=args.plugin_id,
        license_type=args.license_type,
        expires_at=args.expires,
        offline_grace_until=args.grace,
    )
    try:
        token.signature = sign(args.key, token.signing_payload())
    except SigningUnavailableError as exc:
        raise SystemExit(str(exc)) from exc
    payload = token.model_dump_json(by_alias=True, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"Wrote license token for {token.plugin_id} -> {args.out}")
    else:
        print(payload)


def _plugin_license_import(args: argparse.Namespace) -> None:
    from app.plugins.licensing import LicenseCache, LicenseToken

    try:
        token = LicenseToken.model_validate_json(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not read token: {exc}") from exc
    LicenseCache().save(token)
    print(f"Imported license for {token.plugin_id} (user {token.user_id}, expires {token.expires_at}).")


def _plugin_license_status(args: argparse.Namespace) -> None:
    from app.plugins.licensing import LicenseCache, evaluate_token, verify_token

    token = LicenseCache().load(args.plugin_id)
    if token is None:
        print(f"No cached license for {args.plugin_id}.")
        return
    print(f"Plugin:  {token.plugin_id}")
    print(f"User:    {token.user_id}")
    print(f"Type:    {token.license_type}")
    print(f"Expires: {token.expires_at}  (offline grace until {token.offline_grace_until})")
    if args.key:
        status = evaluate_token(token, verified=verify_token(token, args.key))
        print(f"Status:  {'valid' if status.valid else 'invalid'} — {status.reason}")
    else:
        print("Status:  signature not checked (pass --key <issuer public hex> to verify)")


def _plugin_licenses(args: argparse.Namespace) -> None:
    from app.plugins.license_scan import scan_installed

    packages = scan_installed()
    flagged = [p for p in packages if p.flagged]
    shown = flagged if getattr(args, "flagged_only", False) else packages

    if getattr(args, "output", "table") == "json":
        print(
            json.dumps(
                [{"name": p.name, "version": p.version, "license": p.effective, "flagged": p.flagged} for p in shown],
                indent=2,
            )
        )
    else:
        width = max((len(p.name) for p in shown), default=4)
        for p in shown:
            mark = "  REVIEW" if p.flagged else ""
            print(f"  {p.name.ljust(width)}  {p.version:<12} {p.effective or 'UNKNOWN'}{mark}")
        print(f"\n{len(flagged)} of {len(packages)} packages need review.")

    if getattr(args, "fail_on_flagged", False) and flagged:
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
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
        "plugin": _plugin,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return
    handler(args)


if __name__ == "__main__":  # pragma: no cover
    main()
