from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import datasets, flows, runs, transformations
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.ENVIRONMENT)

    for subdir in ("uploads", "outputs", "previews"):
        Path(settings.DATA_DIR, subdir).mkdir(parents=True, exist_ok=True)

    yield


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

    app.include_router(flows.router, prefix="/api/flows", tags=["flows"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(runs.router, prefix="/api", tags=["runs"])
    app.include_router(
        transformations.router, prefix="/api/transformations", tags=["transformations"]
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
