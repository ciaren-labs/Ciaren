# SPDX-License-Identifier: AGPL-3.0-only
"""Single place that mounts every API router onto the app.

Registration order matters: the frontend SPA catch-all (mounted later, in
:func:`app.bootstrap.frontend.mount_frontend`) only takes paths the routers here
didn't claim, so all ``/api/*`` and health routes must be included first.

Prefix conventions (see app/README.md):
- Top-level collections mount at ``/api/<resource>`` (projects, flows, datasets, …).
- Routers that own nested/sibling paths (runs → ``/api/flows/{id}/runs`` +
  ``/api/runs``; ml, schedules, webhooks) mount at the bare ``/api`` prefix and
  declare their full paths internally.
"""

from fastapi import FastAPI

from app.api.routes import (
    catalog,
    connections,
    datasets,
    flows,
    health,
    marketplace,
    ml,
    plugins,
    projects,
    runs,
    schedules,
    transformations,
    webhooks,
)
from app.api.routes import settings as settings_routes


def register_routers(app: FastAPI) -> None:
    app.include_router(health.router)
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
    # Registered after webhooks so the legacy GET /api/settings/webhook keeps
    # resolving there; the settings router has no GET /{key}, so today there is
    # no overlap — keep it that way (add-only PUT/DELETE per key).
    app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
