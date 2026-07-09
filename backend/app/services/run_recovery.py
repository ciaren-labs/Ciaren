# SPDX-License-Identifier: AGPL-3.0-only
"""Startup recovery of runs interrupted by a crash or restart.

The app is single-process, so any :class:`FlowRun` still in ``running`` when the
process starts was interrupted mid-flight and can never complete. Marking those
failed keeps run history honest and clears them from "active" listings.

This lives outside the scheduler on purpose: the recovery must happen at
application startup **regardless of ``SCHEDULER_ENABLED``**. Wiring it only into
``SchedulerRunner.start()`` meant a deployment with the scheduler disabled would
leave interrupted runs stuck in ``running`` forever.

Single-process assumption: it uses global ``status == "running"`` as the orphan
signal, so it is only safe under the project's single-process design (matching
the in-memory cancellation registry, in-process scheduler, and in-memory overlap
guard). Under ``gunicorn -w N`` or an overlapping/rolling restart, a booting
process would mark another live process's genuinely-running run as failed. If
multi-process is ever supported, scope this to runs older than a startup
threshold or tag runs with a process/boot id.
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.run import FlowRun

logger = logging.getLogger("ciaren.startup")

_INTERRUPTED_MESSAGE = "Run interrupted by a server restart."


async def recover_orphaned_runs(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Mark every run still ``running`` as failed. Idempotent; returns the count."""
    now = datetime.now(UTC).replace(tzinfo=None)
    async with session_factory() as db:
        result = cast(
            CursorResult[Any],
            await db.execute(
                update(FlowRun)
                .where(FlowRun.status == "running")
                .values(
                    status="failed",
                    error_message=_INTERRUPTED_MESSAGE,
                    finished_at=now,
                )
            ),
        )
        count = result.rowcount or 0
        if count:
            logger.warning("Recovered %s orphaned run(s) after restart", count)
        await db.commit()
    return count
