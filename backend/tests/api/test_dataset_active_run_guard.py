# SPDX-License-Identifier: AGPL-3.0-only
"""Purging a dataset unlinks its version files immediately (unlike soft-delete),
so a run still reading those files must block the purge (409) instead of racing
a mid-run filesystem error. Overridable with ?force=true. purge_expired() (the
retention sweep) defers instead of raising, since there's no caller to refuse."""

import io
from datetime import UTC, datetime, timedelta

import pandas as pd
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import FlowRun
from app.services.dataset_service import DatasetService


async def _upload(client: AsyncClient, name: str = "d.csv") -> dict:
    df = pd.DataFrame({"a": [1, 2, 3]})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _flow(client: AsyncClient, dataset_id: str, name: str = "f") -> dict:
    graph = {
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}}],
        "edges": [],
    }
    r = await client.post("/api/flows", json={"name": name, "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def _insert_active_run(db_session: AsyncSession, flow_id: str, dataset_id: str, status: str = "running") -> None:
    db_session.add(FlowRun(flow_id=flow_id, input_dataset_id=dataset_id, status=status))
    await db_session.commit()


async def test_purge_blocked_while_run_is_active(client: AsyncClient, db_session: AsyncSession) -> None:
    ds = await _upload(client)
    flow = await _flow(client, ds["id"])
    await _insert_active_run(db_session, flow["id"], ds["id"])

    blocked = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True})
    assert blocked.status_code == 409
    assert flow["name"] in blocked.json()["detail"]

    forced = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True, "force": True})
    assert forced.status_code == 204


async def test_purge_blocked_by_multi_input_run_via_input_datasets_json(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # A join/concat flow's non-primary input only appears in input_datasets_json,
    # not input_dataset_id — the guard must check both.
    ds = await _upload(client)
    other = await _upload(client, name="other.csv")
    flow = await _flow(client, other["id"])
    db_session.add(
        FlowRun(
            flow_id=flow["id"],
            input_dataset_id=other["id"],
            input_datasets_json=[{"dataset_id": ds["id"], "version": 1}],
            status="running",
        )
    )
    await db_session.commit()

    blocked = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True})
    assert blocked.status_code == 409


async def test_purge_allowed_once_run_finishes(client: AsyncClient, db_session: AsyncSession) -> None:
    ds = await _upload(client)
    flow = await _flow(client, ds["id"])
    await _insert_active_run(db_session, flow["id"], ds["id"], status="success")

    ok = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True})
    assert ok.status_code == 204


async def test_soft_delete_not_blocked_by_active_run(client: AsyncClient, db_session: AsyncSession) -> None:
    # Soft-delete retains the files (restorable), so it's safe even mid-run —
    # only a purge (which unlinks files immediately) needs the guard.
    ds = await _upload(client)
    flow = await _flow(client, ds["id"])
    await _insert_active_run(db_session, flow["id"], ds["id"])

    ok = await client.delete(f"/api/datasets/{ds['id']}")
    assert ok.status_code == 204


async def test_purge_expired_defers_dataset_in_use_by_active_run(client: AsyncClient, db_session: AsyncSession) -> None:
    ds = await _upload(client)
    flow = await _flow(client, ds["id"])
    await _insert_active_run(db_session, flow["id"], ds["id"])

    soft = await client.delete(f"/api/datasets/{ds['id']}")
    assert soft.status_code == 204

    service = DatasetService(db_session)
    far_future = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3650)
    purged = await service.purge_expired(now=far_future)
    assert purged == 0

    # Still there — the dataset was deferred, not silently dropped.
    get_ds = await client.get(f"/api/datasets/{ds['id']}")
    assert get_ds.status_code == 200
