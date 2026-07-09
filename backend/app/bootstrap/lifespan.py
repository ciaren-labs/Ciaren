# SPDX-License-Identifier: AGPL-3.0-only
"""Application startup/shutdown lifecycle.

Ordered so each step can rely on the previous: logging → data dirs → schema →
persisted setting overrides → plugins → seeding → orphaned-run recovery →
scheduler. Every optional step is best-effort and must never block the server
from coming up.

The symbols used here (``init_db``, ``AsyncSessionLocal``, ``get_settings``, and the
seeding helpers) are imported at module scope on purpose: it keeps the startup
sequence readable and lets lifecycle tests patch ``app.bootstrap.lifespan.<name>``
without standing up the whole app.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.bootstrap.seeding import (
    run_seeded_flows_safe,
    seed_demo_safe,
    seed_local_storage_safe,
    seed_mlflow_connection_safe,
)
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.logging import setup_logging
from app.services.run_recovery import recover_orphaned_runs

logger = logging.getLogger("ciaren.bootstrap")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.ENVIRONMENT, debug=settings.DEBUG, log_format=settings.LOG_FORMAT)

    for subdir in ("uploads", "outputs", "previews"):
        Path(settings.DATA_DIR, subdir).mkdir(parents=True, exist_ok=True)

    await init_db()

    # Re-apply persisted setting overrides (Settings page) so they take
    # precedence over env/defaults for everything below (scheduler, seeds) and
    # for request handling. Best-effort: a bad row is skipped, never fatal.
    try:
        from app.core.runtime_settings import load_and_apply_overrides

        async with AsyncSessionLocal() as session:
            await load_and_apply_overrides(session)
    except Exception:  # noqa: BLE001 - settings overrides must never block startup
        logger.warning("Could not load persisted app settings; using env/defaults.", exc_info=True)

    # Discover plugins and bridge their executable nodes into the engine registry
    # before any request, so a run that uses a plugin node resolves it even if the
    # catalog endpoint was never hit first.
    from app.plugins import ensure_plugins_loaded

    ensure_plugins_loaded()

    await seed_local_storage_safe(settings.DATA_DIR)

    if settings.ML_ENABLED:
        await seed_mlflow_connection_safe(settings.MLFLOW_TRACKING_URI)

    if settings.SEED_DEMO:
        seeded_project_id = await seed_demo_safe()
        if seeded_project_id is not None and settings.SEED_RUN_FLOWS:
            logger.info("Running seeded demo flows once (SEED_RUN_FLOWS enabled)…")
            await run_seeded_flows_safe(seeded_project_id)

    # Recover runs left in ``running`` by a crash/restart. Done here — not only in
    # the scheduler — so it happens even when SCHEDULER_ENABLED is false; otherwise
    # interrupted runs would stay stuck in ``running`` indefinitely. Best-effort:
    # a recovery failure must not block startup.
    try:
        await recover_orphaned_runs(AsyncSessionLocal)
    except Exception:  # noqa: BLE001 - startup must proceed even if recovery fails
        logger.warning("Orphaned-run recovery failed; continuing.", exc_info=True)

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
