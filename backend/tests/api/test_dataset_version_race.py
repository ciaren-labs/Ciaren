# SPDX-License-Identifier: AGPL-3.0-only
"""Two concurrent uploads/output-writes to the same dataset can race on the next
version number: both read the same max(version_number) before either commits.
_add_version_with_retry retries against a fresh max instead of letting the DB's
unique constraint surface as a raw 500 (upload) or a silently dropped
registration (run output)."""

import io

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.services.dataset_service import DatasetService


async def _upload(client: AsyncClient) -> dict:
    df = pd.DataFrame({"a": [1, 2, 3]})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _get_dataset(db_session: AsyncSession, dataset_id: str) -> Dataset:
    result = await db_session.execute(select(Dataset).where(Dataset.id == dataset_id))
    return result.scalar_one()


async def test_retry_recovers_when_a_concurrent_writer_wins_the_race(
    client: AsyncClient, db_session: AsyncSession, engine: AsyncEngine
) -> None:
    """Simulates the real race: our own attempt reads max()=1, but before we
    flush, an independent session commits version 2 first. The retry must
    requery max() (now 2) and land on 3, rather than repeatedly colliding."""
    ds = await _upload(client)  # creates version 1
    dataset = await _get_dataset(db_session, ds["id"])
    service = DatasetService(db_session)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    original_next = service._next_version_number
    calls = 0

    async def flaky_next_version_number(dataset_id: str) -> int:
        nonlocal calls
        calls += 1
        number = await original_next(dataset_id)
        if calls == 1:
            # A "concurrent request" grabs this exact number first, via an
            # independent session that commits before our own flush.
            async with factory() as other:
                other.add(DatasetVersion(dataset_id=dataset_id, version_number=number, location="x", row_count=0))
                await other.commit()
        return number

    service._next_version_number = flaky_next_version_number  # type: ignore[method-assign]

    version = await service._add_version_with_retry(
        dataset,
        lambda n: DatasetVersion(dataset_id=dataset.id, version_number=n, location="y", row_count=1),
    )
    await db_session.commit()

    assert calls == 2  # first attempt collided, second succeeded
    assert version.version_number == 3


async def test_retry_gives_up_after_max_attempts_with_a_clean_conflict_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ds = await _upload(client)
    dataset = await _get_dataset(db_session, ds["id"])
    service = DatasetService(db_session)

    async def always_stale_next_version_number(_dataset_id: str) -> int:
        return 1  # always collides with the version 1 row that already exists

    service._next_version_number = always_stale_next_version_number  # type: ignore[method-assign]

    with pytest.raises(ConflictError):
        await service._add_version_with_retry(
            dataset,
            lambda n: DatasetVersion(dataset_id=dataset.id, version_number=n, location="y", row_count=1),
        )
    # The session must stay usable after exhausting retries — each failed
    # attempt was contained in its own savepoint, not the outer transaction.
    await db_session.execute(select(Dataset).where(Dataset.id == ds["id"]))


async def test_upload_race_returns_409_not_500(client: AsyncClient) -> None:
    """End-to-end: force the exhausted-retries path through the real upload()
    endpoint and confirm it surfaces as a clean 409, not a raw 500."""
    await _upload(client)  # version 1 already exists for this dataset name

    async def always_stale_next_version_number(_self: DatasetService, _dataset_id: str) -> int:
        return 1  # always collides with the existing version 1 row

    # Monkeypatch at the class level so the DatasetService instance the route
    # constructs for this request picks up the flaky method.
    original_method = DatasetService._next_version_number
    DatasetService._next_version_number = always_stale_next_version_number  # type: ignore[method-assign]
    try:
        buf = io.BytesIO()
        pd.DataFrame({"a": [9]}).to_csv(buf, index=False)
        r = await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})
        assert r.status_code == 409, r.text
    finally:
        DatasetService._next_version_number = original_method
