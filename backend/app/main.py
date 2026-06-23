import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    connections,
    datasets,
    flows,
    ml,
    projects,
    runs,
    schedules,
    transformations,
)
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, init_db
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
            result = await session.execute(
                select(Connection).where(Connection.provider == "local").limit(1)
            )
            if result.scalars().first() is None:
                conn = Connection(name="Local Storage", provider="local", database=data_dir)
                session.add(conn)
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.warning("Local Storage seeding failed; continuing without it.", exc_info=True)


async def _seed_demo_safe() -> None:
    """Seed the demo project, never letting a failure block startup.

    Seeding is idempotent (a no-op once the Demo project exists), so this is
    safe to run on every boot. Any error is logged as a warning and swallowed.
    """
    try:
        from app.demo import seed_demo

        async with AsyncSessionLocal() as session:
            await seed_demo(session)
    except Exception:  # noqa: BLE001 - seeding must never crash the server
        logger.warning("Demo project seeding failed; continuing without it.", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.ENVIRONMENT, debug=settings.DEBUG)

    for subdir in ("uploads", "outputs", "previews"):
        Path(settings.DATA_DIR, subdir).mkdir(parents=True, exist_ok=True)

    await init_db()

    await _seed_local_storage_safe(settings.DATA_DIR)

    if settings.SEED_DEMO:
        await _seed_demo_safe()

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

    app = FastAPI(
        title=settings.APP_NAME,
        description="Visual ETL builder — local-first, dataframe-based",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept"],
    )

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

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    _mount_frontend(app, settings)

    return app


def frontend_dist_path(settings: object | None = None) -> Path | None:
    """Resolve the built frontend directory, or None if it isn't available.

    Uses FRONTEND_DIST when set, else the repo's frontend/dist (dev checkout).
    Only returns a path that actually contains an index.html.
    """
    if settings is None:
        settings = get_settings()
    configured = getattr(settings, "FRONTEND_DIST", None)
    dist = Path(configured) if configured else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return dist if (dist / "index.html").is_file() else None


def _mount_frontend(app: FastAPI, settings: object) -> None:
    """Serve the built web UI (with SPA fallback) when it's available, so the
    whole app is reachable at the server URL. No-op when the frontend isn't built."""
    dist = frontend_dist_path(settings)
    if dist is None:
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index = dist / "index.html"

    # Catch-all for client-side routes: serve real files, else the SPA shell.
    # /api, /health, /docs are matched by their routes above (registered first).
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> Response:
        if path.startswith("api/") or path in ("health", "openapi.json"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = (dist / path).resolve()
        # Guard against path traversal escaping the dist dir.
        if candidate.is_file() and str(candidate).startswith(str(dist.resolve())):
            return FileResponse(str(candidate))
        return FileResponse(str(index))


app = create_app()
