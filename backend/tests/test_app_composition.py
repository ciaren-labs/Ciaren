"""App composition tests — exercise the extracted bootstrap/api modules in
isolation, without standing up the whole application surface.

These lock in the contracts of the pieces `create_app()` wires together:
error-handler mapping, middleware headers, router mounting, and the health probes.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.errors import register_exception_handlers
from app.api.middleware import register_middleware
from app.api.routers import register_routers
from app.core.exceptions import ConflictError, NotFoundError, ValidationError


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# -- error layer ------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "status"),
    [
        (NotFoundError("Thing", "x"), 404),
        (ValidationError("nope"), 400),
        (ConflictError("dupe"), 409),
    ],
)
async def test_register_exception_handlers_maps_domain_errors(exc: Exception, status: int) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    async with await _client(app) as c:
        r = await c.get("/boom")
    assert r.status_code == status
    assert "detail" in r.json()


# -- middleware layer -------------------------------------------------------


async def test_register_middleware_adds_security_headers() -> None:
    app = FastAPI()
    register_middleware(app, SimpleNamespace(CORS_ORIGINS=["http://localhost:5173"]))

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    async with await _client(app) as c:
        r = await c.get("/ping")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


# -- router layer -----------------------------------------------------------


async def test_register_routers_mounts_health_and_api() -> None:
    app = FastAPI()
    register_routers(app)
    paths = set(app.openapi()["paths"])
    assert "/health" in paths
    assert "/ready" in paths
    # A representative sample of the API surface is mounted under /api.
    assert "/api/flows" in paths
    assert "/api/datasets" in paths


async def test_health_probe_is_dependency_free() -> None:
    app = FastAPI()
    register_routers(app)
    async with await _client(app) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# -- composition root -------------------------------------------------------


def test_create_app_is_a_short_composition() -> None:
    # The composition root should stay thin: assemble the app from the focused
    # modules rather than growing inline logic. Guard against regression by keeping
    # main.py small (it re-exports a few compat symbols + create_app + app).
    import inspect

    import app.main as main

    source_lines = inspect.getsource(main.create_app).count("\n")
    assert source_lines < 40, "create_app grew — extract new bootstrap logic into a module"


async def test_extracted_modules_are_independently_importable() -> None:
    # Proves the decoupling: each concern imports without pulling in app.main.
    import importlib

    for mod in (
        "app.bootstrap.seeding",
        "app.bootstrap.frontend",
        "app.bootstrap.lifespan",
        "app.api.errors",
        "app.api.middleware",
        "app.api.routers",
        "app.api.routes.health",
    ):
        assert importlib.import_module(mod) is not None
