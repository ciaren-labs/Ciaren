"""FlowFrame command-line entry point.

Exposed as the ``flowframe`` console script (see ``[project.scripts]``), so a
``pip install flowframe`` is followed by a single command to run everything:

    flowframe serve

``serve`` boots the FastAPI app in one process; the app's lifespan starts the
background scheduler, so the API and scheduled runs share that single process —
no broker, no extra services. Uses only argparse (stdlib) to keep setup trivial.
"""

import argparse
import os
from importlib.metadata import PackageNotFoundError, version


def _package_version() -> str:
    try:
        return version("flowframe")
    except PackageNotFoundError:  # pragma: no cover - running from a source checkout
        return "0.0.0"


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
        "--no-scheduler",
        action="store_true",
        help="Start the API without the background scheduler.",
    )
    return parser


def _apply_serve_env(args: argparse.Namespace) -> None:
    """Translate serve flags into the env vars the Settings layer reads, before the
    app (and its cached settings) are imported."""
    if args.db_url:
        os.environ["FLOWFRAME_DATABASE_URL"] = args.db_url
    if args.no_scheduler:
        os.environ["FLOWFRAME_SCHEDULER_ENABLED"] = "false"


def _serve(args: argparse.Namespace) -> None:
    _apply_serve_env(args)
    import uvicorn

    # Pass the import string (not the app object) so --reload works.
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        _serve(args)
    else:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover
    main()
