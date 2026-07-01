"""Edge cases found in the 2026-07 backend audit (Phases 2-3).

Phase 2 (routes & services): flow moves to nonexistent projects, soft-delete
state consistency when re-enabling datasets (directly or via project cascade),
pagination bounds on the schedule-runs listing, and the upload error message
listing every allowed type.

Phase 3 (execution pipeline): empty-graph preview, unconfigured input nodes,
SQL nodes bound to non-database connections, and the started_after/-before
run filters actually filtering on started_at.
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


# -- Phase 3: preview / execution edge cases ------------------------------------


async def test_preview_empty_flow_is_400_not_500(client: AsyncClient) -> None:
    flow = await _create_flow(client)  # empty graph
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text
    assert "no nodes" in r.json()["detail"].lower()


async def test_preview_dangling_edge_is_400_not_500(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = {
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}}],
        "edges": [{"id": "e1", "source": "in1", "target": "ghost"}],
    }
    flow = await _create_flow(client, graph_json=graph)
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text


async def test_preview_unconfigured_input_node_gives_clear_400(client: AsyncClient) -> None:
    """An input node without a dataset (e.g. a freshly imported flow) must fail
    with a clear message, not a bare KeyError('dataset_id')."""
    graph = {
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}],
        "edges": [],
    }
    flow = await _create_flow(client, graph_json=graph)
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text
    assert "no dataset selected" in r.json()["detail"]


async def test_sql_node_bound_to_storage_connection_gives_clear_error(client: AsyncClient, tmp_path) -> None:
    conn = (
        await client.post(
            "/api/connections",
            json={"name": "audit local storage", "provider": "local", "database": str(tmp_path / "store")},
        )
    ).json()
    graph = {
        "nodes": [
            {
                "id": "sql1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": conn["id"], "mode": "table", "table": "t"}},
            }
        ],
        "edges": [],
    }
    flow = await _create_flow(client, graph_json=graph)
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text
    assert "not a database connection" in r.json()["detail"]


async def test_started_after_filter_uses_started_at(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow = await _create_flow(client, graph_json=graph)
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success"

    listed = (await client.get("/api/runs", params={"started_after": "2000-01-01T00:00:00"})).json()
    assert run["id"] in [x["id"] for x in listed]
    listed = (await client.get("/api/runs", params={"started_after": "2100-01-01T00:00:00"})).json()
    assert run["id"] not in [x["id"] for x in listed]
    listed = (await client.get("/api/runs", params={"started_before": "2000-01-01T00:00:00"})).json()
    assert run["id"] not in [x["id"] for x in listed]
