# SPDX-License-Identifier: AGPL-3.0-only
"""One-time, best-effort startup seeding.

Every function here is idempotent and swallows its own errors (logging a warning):
seeding a fresh install with helpful defaults must never block the server from
starting. Called from :mod:`app.bootstrap.lifespan`.
"""

import logging

from app.core.database import AsyncSessionLocal

logger = logging.getLogger("ciaren.seeding")


async def seed_local_storage_safe(data_dir: str) -> None:
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


async def seed_mlflow_connection_safe(tracking_uri: str) -> None:
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


async def seed_demo_safe() -> str | None:
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


async def run_seeded_flows_safe(project_id: str) -> None:
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
