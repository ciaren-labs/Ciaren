# SPDX-License-Identifier: AGPL-3.0-only
"""Serve the built web UI (with SPA fallback) from the API process.

No-op when the frontend isn't built, so an API-only deployment just skips it.
"""

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings


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
    # app/bootstrap/frontend.py → parents[1] is app/, so app/web is parents[1]/web,
    # and the repo's frontend/dist is parents[3]/frontend/dist.
    candidates.append(here.parents[1] / "web")  # bundled into the wheel
    candidates.append(here.parents[3] / "frontend" / "dist")  # source checkout
    for dist in candidates:
        if (dist / "index.html").is_file():
            return dist
    return None


# Correct Content-Type for the web bundle's file types. Python's ``mimetypes`` seeds
# itself from the OS: on Windows the registry frequently maps ``.js`` to
# ``text/plain``, which makes browsers refuse the ES module scripts (strict MIME
# checking) so the SPA renders a blank page. Forcing these overrides the registry for
# the process and fixes both the ``/assets`` StaticFiles mount and the SPA
# ``FileResponse`` fallback, since both resolve types through ``mimetypes``.
_WEB_MIME_TYPES: dict[str, str] = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def _ensure_web_mime_types() -> None:
    for ext, media_type in _WEB_MIME_TYPES.items():
        mimetypes.add_type(media_type, ext)


def mount_frontend(app: FastAPI, settings: object) -> None:
    """Serve the built web UI (with SPA fallback) when it's available, so the whole
    app is reachable at the server URL. No-op when the frontend isn't built.

    Hashed assets get a long immutable cache; index.html is never cached so a new
    build is picked up immediately. GZip is handled by app-level middleware.
    """
    dist = frontend_dist_path(settings)
    if dist is None:
        return

    # Must run before any static file is served so the right Content-Type is sent.
    _ensure_web_mime_types()

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
