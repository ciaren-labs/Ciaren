# SPDX-License-Identifier: AGPL-3.0-only
"""Liveness and readiness probes for container orchestrators / load balancers."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger("app.health")

router = APIRouter()


@router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness: the process is up and serving. No dependencies are checked,
    so a container orchestrator can restart a hung process without being
    misled by a transient database blip."""
    return {"status": "ok"}


@router.get("/ready", tags=["health"])
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
