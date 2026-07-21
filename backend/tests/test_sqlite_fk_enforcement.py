# SPDX-License-Identifier: AGPL-3.0-only
"""SQLite foreign-key enforcement is ON for app-configured engines.

SQLite ships with ``PRAGMA foreign_keys`` OFF per connection, which turns every
``ondelete`` rule in the models into a no-op — deletes could leave dangling
references (e.g. a purged dataset still pointed at by
``flow_runs.input_dataset_id``). ``app.core.database.enable_sqlite_foreign_keys``
registers a connect-time PRAGMA listener; these tests prove the pragma is live
on real connections and that violations are actually rejected.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import _make_engine
from app.db.models.dataset_version import DatasetVersion
from app.db.models.run import FlowRun


async def test_app_engine_turns_sqlite_foreign_keys_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """The production engine factory must emit PRAGMA foreign_keys=ON on every
    new SQLite connection (the pragma is connection-scoped, not database-scoped)."""
    monkeypatch.setenv("CIAREN_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    try:
        app_engine = _make_engine()
        try:
            async with app_engine.connect() as conn:
                result = await conn.exec_driver_sql("PRAGMA foreign_keys")
                assert result.scalar() == 1
        finally:
            await app_engine.dispose()
    finally:
        get_settings.cache_clear()


async def test_test_engine_turns_sqlite_foreign_keys_on(db_session: AsyncSession) -> None:
    """The test fixtures mirror production enforcement (guards the conftest wiring)."""
    connection = await db_session.connection()
    result = await connection.exec_driver_sql("PRAGMA foreign_keys")
    assert result.scalar() == 1


async def test_orphan_flow_run_is_rejected(db_session: AsyncSession) -> None:
    """A child row pointing at a nonexistent parent must raise, proving
    enforcement is live (previously SQLite accepted it silently)."""
    db_session.add(FlowRun(flow_id=str(uuid.uuid4()), status="pending"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_orphan_dataset_version_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(DatasetVersion(dataset_id=str(uuid.uuid4()), version_number=1, location="x", row_count=0))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
