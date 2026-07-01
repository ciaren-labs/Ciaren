"""Edge cases found in the 2026-07 backend audit (Phase 2: routes & services).

Covers: flow moves to nonexistent projects, soft-delete state consistency when
re-enabling datasets (directly or via project cascade), pagination bounds on the
schedule-runs listing, and the upload error message listing every allowed type.
"""

import io

import pandas as pd
from httpx import AsyncClient


async def _upload(client: AsyncClient, name: str = "audit.csv") -> dict:
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, **overrides) -> dict:
    payload = {"name": "audit flow", "graph_json": {"nodes": [], "edges": []}, **overrides}
    r = await client.post("/api/flows", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# -- flow update project binding ---------------------------------------------


async def test_flow_update_rejects_unknown_project(client: AsyncClient) -> None:
    flow = await _create_flow(client)
    r = await client.put(f"/api/flows/{flow['id']}", json={"project_id": "no-such-project"})
    assert r.status_code == 404, r.text
    # The flow keeps its original project.
    fetched = (await client.get(f"/api/flows/{flow['id']}")).json()
    assert fetched["project_id"] == flow["project_id"]


async def test_flow_update_moves_to_existing_project(client: AsyncClient) -> None:
    flow = await _create_flow(client)
    proj = (await client.post("/api/projects", json={"name": "audit target"})).json()
    r = await client.put(f"/api/flows/{flow['id']}", json={"project_id": proj["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["project_id"] == proj["id"]


# -- dataset re-enable clears soft-delete --------------------------------------


async def test_patch_enable_clears_deleted_at(client: AsyncClient) -> None:
    ds = await _upload(client)
    await client.delete(f"/api/datasets/{ds['id']}")
    r = await client.patch(f"/api/datasets/{ds['id']}", json={"is_disabled": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_disabled"] is False
    # Re-enabling must also lift the soft-delete, or the dataset would look live
    # while still being eligible for the retention purge.
    assert body["deleted_at"] is None


async def test_project_reenable_does_not_revive_soft_deleted_dataset(client: AsyncClient) -> None:
    proj = (await client.post("/api/projects", json={"name": "audit cascade"})).json()
    buf = io.BytesIO()
    pd.DataFrame({"a": [1]}).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        params={"project_id": proj["id"]},
        files={"file": ("cascade.csv", buf.getvalue(), "text/csv")},
    )
    ds = r.json()
    await client.delete(f"/api/datasets/{ds['id']}")

    # Disable then re-enable the whole project.
    await client.put(f"/api/projects/{proj['id']}", json={"is_disabled": True})
    await client.put(f"/api/projects/{proj['id']}", json={"is_disabled": False})

    fetched = (await client.get(f"/api/datasets/{ds['id']}")).json()
    assert fetched["deleted_at"] is not None
    assert fetched["is_disabled"] is True


# -- schedule runs pagination bounds -------------------------------------------


async def test_schedule_runs_rejects_negative_pagination(client: AsyncClient) -> None:
    flow = await _create_flow(client)
    r = await client.post(
        f"/api/flows/{flow['id']}/schedules",
        json={"cron": "0 * * * *"},
    )
    assert r.status_code == 201, r.text
    schedule_id = r.json()["id"]

    r = await client.get(f"/api/schedules/{schedule_id}/runs", params={"limit": -5})
    assert r.status_code == 422, r.text
    r = await client.get(f"/api/schedules/{schedule_id}/runs", params={"offset": -1})
    assert r.status_code == 422, r.text


# -- upload error message lists every allowed type ------------------------------


async def test_unsupported_upload_error_lists_all_allowed_types(client: AsyncClient) -> None:
    r = await client.post("/api/datasets/upload", files={"file": ("data.foo", b"x", "text/plain")})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    for ext in (".csv", ".tsv", ".xlsx", ".parquet", ".json", ".jsonl", ".txt"):
        assert ext in detail, f"{ext} missing from: {detail}"
