# SPDX-License-Identifier: AGPL-3.0-only
"""FastAPI application composition root.

``create_app()`` is deliberately short: it wires together the pieces that live in
focused modules — middleware, error handlers, routers, the frontend mount — and the
startup/shutdown lifecycle in :mod:`app.bootstrap.lifespan`. Keeping the assembly
here (and the details there) means a cross-cutting change touches one small,
well-named module instead of this bootstrap file.
"""

from fastapi import Depends, FastAPI

from app.api.errors import register_exception_handlers
from app.api.middleware import register_middleware
from app.api.routers import register_routers

# ``_ensure_web_mime_types`` and ``frontend_dist_path`` are re-exported (see
# __all__) so ``from app.main import ...`` keeps working for the CLI and tests.
from app.bootstrap.frontend import _ensure_web_mime_types, frontend_dist_path, mount_frontend
from app.bootstrap.lifespan import lifespan
from app.core.config import get_settings
from app.version import ciaren_version

__all__ = ["app", "create_app", "lifespan", "frontend_dist_path", "_ensure_web_mime_types"]


def create_app() -> FastAPI:
    settings = get_settings()

    from app.core.auth import verify_api_token
    from app.core.csrf import verify_browser_origin

    app = FastAPI(
        title="Ciaren",
        description="Visual data and ML workflow builder — local-first, dataframe-based",
        version=ciaren_version(),
        lifespan=lifespan,
        # Optional API-token gate (no-op unless CIAREN_API_TOKEN is set) plus the
        # browser-origin CSRF guard for the unauthenticated local posture. As
        # dependencies rather than middleware, a 401/403 still passes through CORS.
        dependencies=[Depends(verify_api_token), Depends(verify_browser_origin)],
    )

    register_middleware(app, settings)
    register_exception_handlers(app)
    register_routers(app)
    mount_frontend(app, settings)

    return app


app = create_app()
