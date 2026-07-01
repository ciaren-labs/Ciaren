# SPDX-License-Identifier: AGPL-3.0-only
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import (
    catalog,
    connections,
    datasets,
    flows,
    marketplace,
    ml,
    plugins,
    projects,
    runs,
    schedules,
    transformations,
    webhooks,
)
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, get_db, init_db
from app.core.exceptions import (
    ConflictError,
    DatasetParseError,
    FileTooLargeError,
    MLNotEnabledError,
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.core.logging import setup_logging

logger = logging.getLogger("app.main")


async def _seed_local_storage_safe(data_dir: str) -> None:
    """Ensure the built-in 'Local Storage' connection exists. Idempotent."""
    try:
        from sqlalchemy import select

        from app.db.models.connection import Connection

        async with AsyncSessionLocal() as session:
            # Use first() (not scalar_one_or_none): tolerate pre-existing duplicate
            # rows from older builds instead of crashing startup seeding.
            result = await session.execute(select(Connection).where(Connection.provider == "local").limit(1))
            if result.scalars().first() is None:
                conn = Connection(name="Local Storage", provider="local", database=data_dir)
                session.add(conn)
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("Local Storage seeding failed; continuing without it.", exc_info=True)


async def _seed_mlflow_connection_safe(tracking_uri: str) -> None:
    """Ensure a built-in 'Local MLflow' connection exists (the default tracking
    store, editable by the user). Idempotent and best-effort.

    This is the source of truth for the MLflow tracking URI: once it exists, runs
    and the ML pages resolve the URI from it, so editing it re-points MLflow."""
    try:
        from sqlalchemy import select

        from app.db.models.connection import Connection

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Connection).where(Connection.provider == "mlflow").limit(1))
            if result.scalars().first() is None:
                conn = Connection(name="Local MLflow", provider="mlflow", database=tracking_uri)
                session.add(conn)
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("MLflow connection seeding failed; continuing without it.", exc_info=True)


async def _seed_demo_safe() -> str | None:
    """Seed the demo project, never letting a failure block startup.

    Seeding is idempotent (a no-op once the Demo project exists), so this is
    safe to run on every boot. Any error is logged as a warning and swallowed.
    Returns the new project's id when it was just created (so its flows can be
    run once), or None when seeding was skipped or failed.
    """
    try:
        from app.demo import seed_demo

        async with AsyncSessionLocal() as session:
            project = await seed_demo(session)
            return project.id if project is not None else None
    except Exception:  # noqa: BLE001 - seeding must never crash the server
        logger.warning("Demo project seeding failed; continuing without it.", exc_info=True)
        return None


async def _run_seeded_flows_safe(project_id: str) -> None:
    """Run every flow in the freshly-seeded demo project once, best-effort.

    Populates run history (and, for the ML flows, MLflow experiments/models) so a
    new install isn't empty. Each flow runs in its own session; one failure never
    blocks the others or startup."""
    try:
        from sqlalchemy import select

        from app.db.models.flow import Flow
        from app.schemas.run import FlowRunCreate
        from app.services.execution_service import ExecutionService

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Flow.id, Flow.name).where(Flow.project_id == project_id))
            flows = result.all()

        for flow_id, flow_name in flows:
            try:
                async with AsyncSessionLocal() as session:
                    await ExecutionService(session).run(flow_id, FlowRunCreate(), trigger="seed")
            except Exception:  # noqa: BLE001 - one bad flow must not stop the rest
                logger.warning("Seed run failed for flow %r; continuing.", flow_name, exc_info=True)
    except Exception:  # noqa: BLE001
        logger.warning("Running seeded flows failed; continuing without it.", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.ENVIRONMENT, debug=settings.DEBUG, log_format=settings.LOG_FORMAT)

    for subdir in ("uploads", "outputs", "previews"):
        Path(settings.DATA_DIR, subdir).mkdir(parents=True, exist_ok=True)

    await init_db()

    # Discover plugins and bridge their executable nodes into the engine registry
    # before any request, so a run that uses a plugin node resolves it even if the
    # catalog endpoint was never hit first.
    from app.plugins import ensure_plugins_loaded

    ensure_plugins_loaded()

    await _seed_local_storage_safe(settings.DATA_DIR)

    if settings.ML_ENABLED:
        await _seed_mlflow_connection_safe(settings.MLFLOW_TRACKING_URI)

    if settings.SEED_DEMO:
        seeded_project_id = await _seed_demo_safe()
        if seeded_project_id is not None and settings.SEED_RUN_FLOWS:
            logger.info("Running seeded demo flows once (SEED_RUN_FLOWS enabled)…")
            await _run_seeded_flows_safe(seeded_project_id)

    runner = None
    if settings.SCHEDULER_ENABLED:
        from app.scheduler import SchedulerRunner

        runner = SchedulerRunner(AsyncSessionLocal, settings)
        await runner.start()

    try:
        yield
    finally:
        if runner is not None:
            await runner.stop()
        # Lazily import so the multiprocessing machinery is only touched when the
        # process pool was actually used (EXECUTION_MODE="process").
        from app.engine.process_pool import shutdown_process_pool

        shutdown_process_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    from app.core.auth import verify_api_token

    app = FastAPI(
        title=settings.APP_NAME,
        description="Visual data and ML workflow builder — local-first, dataframe-based",
        version="0.1.0",
        lifespan=lifespan,
        # Optional API-token gate (no-op unless CIAREN_API_TOKEN is set). As a
        # dependency rather than middleware, a 401 still passes through CORS.
        dependencies=[Depends(verify_api_token)],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Ciaren-Secret"],
    )
    # Compress responses (the served JS/CSS bundle and large JSON payloads).
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedFileTypeError)
    async def unsupported_type_handler(request: Request, exc: UnsupportedFileTypeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(FileTooLargeError)
    async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(DatasetParseError)
    async def parse_error_handler(request: Request, exc: DatasetParseError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(MLNotEnabledError)
    async def ml_not_enabled_handler(request: Request, exc: MLNotEnabledError) -> JSONResponse:
        return JSONResponse(status_code=501, content={"detail": str(exc)})

    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(flows.router, prefix="/api/flows", tags=["flows"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
    app.include_router(runs.router, prefix="/api", tags=["runs"])
    app.include_router(ml.router, prefix="/api", tags=["ml"])
    app.include_router(schedules.router, prefix="/api", tags=["schedules"])
    app.include_router(transformations.router, prefix="/api/transformations", tags=["transformations"])
    app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])
    app.include_router(plugins.router, prefix="/api/plugins", tags=["plugins"])
    app.include_router(marketplace.router, prefix="/api/marketplace", tags=["marketplace"])
    app.include_router(webhooks.router, prefix="/api", tags=["webhook"])

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness: the process is up and serving. No dependencies are checked,
        so a container orchestrator can restart a hung process without being
        misled by a transient database blip."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready(db: AsyncSession = Depends(get_db)) -> Response:
        """Readiness: the process can serve real traffic — i.e. the database is
        reachable. Returns 503 (not 500) when the DB check fails so a load
        balancer drains this instance instead of sending it requests."""
        from sqlalchemy import text

        try:
            await db.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - any DB error means "not ready"
            logger.warning("Readiness check failed: database unreachable.", exc_info=True)
            return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
        return JSONResponse(status_code=200, content={"status": "ok", "database": "up"})

    _mount_frontend(app, settings)

    return app


def frontend_dist_path(settings: object | None = None) -> Path | None:
    """Resolve the built frontend directory, or None if it isn't available.

    Checks, in order: the configured FRONTEND_DIST, the directory bundled inside
    the installed package (``app/web`` — populated at build time), then the repo's
    ``frontend/dist`` (source checkout). Returns the first that has an index.html.
    """
    if settings is None:
        settings = get_settings()
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    configured = getattr(settings, "FRONTEND_DIST", None)
    if configured:
        candidates.append(Path(configured))
    candidates.append(here.parent / "web")  # bundled into the wheel
    candidates.append(here.parents[2] / "frontend" / "dist")  # source checkout
    for dist in candidates:
        if (dist / "index.html").is_file():
            return dist
    return None


def _mount_frontend(app: FastAPI, settings: object) -> None:
    """Serve the built web UI (with SPA fallback) when it's available, so the whole
    app is reachable at the server URL. No-op when the frontend isn't built.

    Hashed assets get a long immutable cache; index.html is never cached so a new
    build is picked up immediately. GZip is handled by app-level middleware.
    """
    dist = frontend_dist_path(settings)
    if dist is None:
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _IMMUTABLE = "public, max-age=31536000, immutable"

    class CachedStatic(StaticFiles):
        # Vite emits content-hashed filenames, so assets can be cached forever.
        async def get_response(self, path: str, scope: Any) -> Response:
            response = await super().get_response(path, scope)
            response.headers.setdefault("Cache-Control", _IMMUTABLE)
            return response

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", CachedStatic(directory=str(assets)), name="assets")

    index = dist / "index.html"

    def _index() -> FileResponse:
        # index.html must not be cached, or clients pin a stale bundle reference.
        return FileResponse(str(index), headers={"Cache-Control": "no-cache"})

    dist_resolved = dist.resolve()

    # Catch-all for client-side routes: serve real files, else the SPA shell.
    # /api, /health, /docs are matched by their routes above (registered first).
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> Response:
        if path.startswith("api/") or path in ("health", "ready", "openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (dist / path).resolve()
        # Guard against path traversal escaping the dist dir. is_relative_to does a
        # real path-component containment check (str.startswith would also accept a
        # sibling dir whose path shares the prefix, e.g. ".../web-secret").
        if candidate.is_file() and candidate.is_relative_to(dist_resolved):
            return FileResponse(str(candidate))
        return _index()


app = create_app()
