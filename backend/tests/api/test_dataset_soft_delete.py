"""Dataset soft-delete: retain on delete, restore, purge (files), retention sweep,
revive-on-reupload, and the clear error when a referenced version file is gone."""

import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.dataset_version import DatasetVersion
from app.services.dataset_service import DatasetService


async def _upload(client: AsyncClient, name: str = "people.csv") -> dict:
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _version_path(db_session, dataset_id: str) -> Path:
    row = await db_session.execute(select(DatasetVersion.location).where(DatasetVersion.dataset_id == dataset_id))
    return Path(row.scalars().first())


# -- soft delete ------------------------------------------------------------


async def test_soft_delete_hides_but_retains(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    path = await _version_path(db_session, ds["id"])
    assert path.exists()

    r = await client.delete(f"/api/datasets/{ds['id']}")
    assert r.status_code == 204

    # excluded from the default list
    listed = (await client.get("/api/datasets")).json()
    assert ds["id"] not in [d["id"] for d in listed]
    # still fetchable, marked deleted, file retained
    fetched = (await client.get(f"/api/datasets/{ds['id']}")).json()
    assert fetched["deleted_at"] is not None
    assert fetched["is_disabled"] is True
    assert path.exists()
    # visible with include_deleted
    listed_all = (await client.get("/api/datasets", params={"include_deleted": True})).json()
    assert ds["id"] in [d["id"] for d in listed_all]


async def test_restore(client: AsyncClient) -> None:
    ds = await _upload(client)
    await client.delete(f"/api/datasets/{ds['id']}")
    restored = (await client.post(f"/api/datasets/{ds['id']}/restore")).json()
    assert restored["deleted_at"] is None
    assert restored["is_disabled"] is False
    assert ds["id"] in [d["id"] for d in (await client.get("/api/datasets")).json()]


async def test_reupload_revives_soft_deleted(client: AsyncClient) -> None:
    ds = await _upload(client, "sales.csv")
    await client.delete(f"/api/datasets/{ds['id']}")
    revived = await _upload(client, "sales.csv")  # same name
    assert revived["id"] == ds["id"]
    assert revived["deleted_at"] is None
    assert revived["version_count"] == 2


# -- purge ------------------------------------------------------------------


async def test_purge_removes_row_and_file(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    path = await _version_path(db_session, ds["id"])
    r = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True})
    assert r.status_code == 204
    assert (await client.get(f"/api/datasets/{ds['id']}")).status_code == 404
    assert not path.exists()


async def test_purge_expired_sweeps_old_soft_deletes(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    path = await _version_path(db_session, ds["id"])
    await client.delete(f"/api/datasets/{ds['id']}")  # soft delete
    # nothing purged yet (within retention)
    assert await DatasetService(db_session).purge_expired() == 0
    assert path.exists()
    # 31 days later, it is swept
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=31)
    purged = await DatasetService(db_session).purge_expired(now=future)
    assert purged == 1
    assert not path.exists()
    assert (await client.get(f"/api/datasets/{ds['id']}")).status_code == 404


async def test_purge_expired_endpoint(client: AsyncClient) -> None:
    r = await client.post("/api/datasets/purge-expired")
    assert r.status_code == 200
    assert "purged" in r.json()


# -- run after a version file is gone ----------------------------------------


async def test_run_with_purged_file_gives_clear_error(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
    # Simulate the file being purged out-of-band while the version row remains.
    (await _version_path(db_session, ds["id"])).unlink()
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "failed"
    assert "no longer available" in run["error_message"]
