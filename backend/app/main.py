import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    connections,
    datasets,
    flows,
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
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.core.logging import setup_logging

logger = logging.getLogger("app.main")


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
    setup_logging(settings.ENVIRONMENT)

    for subdir in ("uploads", "outputs", "previews"):
        Path(settings.DATA_DIR, subdir).mkdir(parents=True, exist_ok=True)

    await init_db()

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
        description="Visual ETL builder — local-first, pandas-based",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(flows.router, prefix="/api/flows", tags=["flows"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
    app.include_router(runs.router, prefix="/api", tags=["runs"])
    app.include_router(schedules.router, prefix="/api", tags=["schedules"])
    app.include_router(transformations.router, prefix="/api/transformations", tags=["transformations"])

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
