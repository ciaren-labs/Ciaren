# SPDX-License-Identifier: AGPL-3.0-only
"""Claim the client's saved revision inside the transaction that uses the graph."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Update

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.flow import Flow


def next_revision(previous: datetime) -> datetime:
    return max(datetime.now(UTC).replace(tzinfo=None), previous + timedelta(microseconds=1))


async def update_one(db: AsyncSession, statement: Update) -> bool:
    # SQLAlchemy requests matched-row semantics on MySQL, including no-op writes.
    result = cast(CursorResult[Any], await db.execute(statement))
    return result.rowcount == 1


async def claim_revision(db: AsyncSession, flow_id: str, revision: datetime | None) -> None:
    if revision is None:
        return  # Older API clients and scheduled jobs use the current saved graph.
    # A conditional UPDATE also serializes writers on SQLite, where SELECT FOR
    # UPDATE is ignored. Preserve the timestamp until a real edit is committed.
    if revision.tzinfo is not None:
        revision = revision.astimezone(UTC).replace(tzinfo=None)
    found = await update_one(
        db, update(Flow).where(Flow.id == flow_id, Flow.updated_at == revision).values(updated_at=Flow.updated_at)
    )
    if not found:
        if not await db.scalar(select(Flow.id).where(Flow.id == flow_id)):
            raise NotFoundError("Flow", flow_id)
        raise ConflictError("The saved flow changed. Open the latest version to compare your draft.")
