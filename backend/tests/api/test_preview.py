"""
Preview endpoint tests.

  GET  /api/transformations
  POST /api/transformations/preview
  POST /api/flows/{flow_id}/preview
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": None, "city": "LA"},
    {"name": "Charlie", "age": 35, "city": "NYC"},
]


def _csv(rows: list[dict] = ROWS) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue()


async def _upload(client: AsyncClient, content: bytes | None = None, filename: str = "test.csv") -> dict:
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (filename, content or _csv(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


# -- GET /api/transformations ------------------------------------------


async def test_list_transformations(client: AsyncClient) -> None:
    r = await client.get("/api/transformations")
    assert r.status_code == 200
    types = r.json()
    assert "dropNulls" in types
    assert "castDtypes" in types


# -- POST /api/transformations/preview ---------------------------------


async def test_preview_transformation_drop_nulls(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2  # one null age row dropped
    assert body["columns"] == ["name", "age", "city"]
    assert body["truncated"] is False


async def test_preview_transformation_with_config(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={
            "type": "renameColumns",
            "dataset_id": ds["id"],
            "config": {"mapping": {"name": "full_name"}},
        },
    )
    assert r.status_code == 200, r.text
    assert "full_name" in r.json()["columns"]


async def test_preview_transformation_limit(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}, "limit": 1},
    )
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["row_count"] == 2
    assert body["truncated"] is True


async def test_preview_transformation_profile_flag(client: AsyncClient) -> None:
    ds = await _upload(client)
    # Without the flag, no profile is computed.
    plain = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}},
    )
    assert plain.json()["profile"] is None

    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}, "profile": True},
    )
    assert r.status_code == 200, r.text
    profile = r.json()["profile"]
    assert profile is not None
    by_name = {p["name"]: p for p in profile}
    assert set(by_name) == {"name", "age", "city"}
    assert by_name["age"]["dtype"] in {"integer", "float"}


async def test_preview_transformation_unknown_type(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "nope", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 404


async def test_preview_transformation_bad_config(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "renameColumns", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 400


async def test_preview_transformation_missing_dataset(client: AsyncClient) -> None:
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": "does-not-exist", "config": {}},
    )
    assert r.status_code == 404


# -- POST /api/flows/{flow_id}/preview ---------------------------------


async def _create_flow(client: AsyncClient, dataset_id: str) -> dict:
    graph = {
        "nodes": [
            {
                "id": "in1",
                "type": "csvInput",
                "data": {"config": {"dataset_id": dataset_id}},
            },
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "drop"}],
    }
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def test_preview_flow_default_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 2  # deepest node = dropNulls


async def test_preview_flow_specific_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "in1"})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 3  # input node, nothing dropped yet


async def test_preview_flow_unknown_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "ghost"})
    assert r.status_code == 404


async def test_preview_flow_missing_flow(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/preview", json={})
    assert r.status_code == 404


async def test_preview_blocked_when_flow_disabled(client: AsyncClient) -> None:
    # Mirrors ExecutionService.run()'s "disabled flow can't run" guard — preview
    # executes real transformation logic too, so it must refuse the same way.
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.put(f"/api/flows/{flow['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text
    assert "disabled" in r.json()["detail"].lower()


async def test_preview_blocked_for_branch_fed_only_by_still_enabled_dataset(client: AsyncClient) -> None:
    """Regression: a flow disabled via one input dataset's cascade must block
    preview of *every* node — including one fed only by a different, still-
    enabled dataset. Previously only ExecutionService.run() enforced this, so a
    disabled flow's data could still be read and transformed through preview."""
    # Distinct filenames: _upload() with the same name would create a second
    # *version* of the same dataset instead of a genuinely separate one.
    ds_a = await _upload(client, filename="a.csv")
    ds_b = await _upload(client, filename="b.csv")
    graph = {
        "nodes": [
            {"id": "in_a", "type": "csvInput", "data": {"config": {"dataset_id": ds_a["id"]}}},
            {"id": "in_b", "type": "csvInput", "data": {"config": {"dataset_id": ds_b["id"]}}},
            {"id": "drop_b", "type": "dropNulls", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in_b", "target": "drop_b"}],
    }
    r = await client.post("/api/flows", json={"name": "multi-input", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    # Disabling dataset A cascades to disable the whole flow, even though the
    # "drop_b" branch is fed only by dataset B, which stays enabled.
    r = await client.patch(f"/api/datasets/{ds_a['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/api/flows/{flow_id}")).json()["is_disabled"] is True

    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "drop_b"})
    assert r.status_code == 400, r.text
    assert "disabled" in r.json()["detail"].lower()


async def test_preview_only_computes_the_upstream_slice(client: AsyncClient) -> None:
    """A failing node elsewhere in the flow (violated assertion) must not break
    previews of nodes that don't depend on it — preview computes only the
    requested node's ancestors."""
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            # A sibling branch whose assertion always fails (needs >= 99 rows).
            {"id": "boom", "type": "assertRowCount", "data": {"config": {"min_rows": 99}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "in1", "target": "boom"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "f2", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    # The clean branch previews fine…
    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "drop"})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 2

    # …while previewing the failing node itself surfaces a clear 400 naming
    # the node (previously an unhandled 500).
    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "boom"})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "boom" in detail and "assertRowCount" in detail
