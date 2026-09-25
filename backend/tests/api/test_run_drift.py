# SPDX-License-Identifier: AGPL-3.0-only
"""Run drift tests — schema/row-count diff vs the previous run of a flow.

GET /api/runs/{run_id}  (the ``drift`` field)
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient

from app.services.execution_service import compute_node_drift

ROWS_A: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": None},
    {"name": "Charlie", "age": 35},
]

ROWS_B: list[dict[str, Any]] = [
    {"name": "a", "age": 1, "city": "x"},
    {"name": "b", "age": 2, "city": "y"},
    {"name": "c", "age": 3, "city": "z"},
    {"name": "d", "age": 4, "city": "w"},
    {"name": "e", "age": 5, "city": "v"},
]


async def _upload(client: AsyncClient, rows: list[dict[str, Any]], name: str) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (name, buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


def _graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "out1"},
        ],
    }


def _graph_with_drop(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


async def _run(client: AsyncClient, flow_id: str) -> dict:
    r = await client.post(f"/api/flows/{flow_id}/runs", json={})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "success"
    return r.json()


async def test_first_run_has_no_drift(client: AsyncClient) -> None:
    ds = await _upload(client, ROWS_A, "a.csv")
    flow = await _create_flow(client, _graph(ds["id"]))
    run = await _run(client, flow["id"])

    fetched = (await client.get(f"/api/runs/{run['id']}")).json()
    assert fetched["drift"] is None


async def test_second_run_shows_row_count_delta(client: AsyncClient) -> None:
    ds1 = await _upload(client, ROWS_A, "a.csv")
    flow = await _create_flow(client, _graph(ds1["id"]))
    run1 = await _run(client, flow["id"])

    ds2 = await _upload(client, ROWS_B, "b.csv")
    upd = await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph(ds2["id"])})
    assert upd.status_code == 200, upd.text
    run2 = await _run(client, flow["id"])

    fetched = (await client.get(f"/api/runs/{run2['id']}")).json()
    drift = fetched["drift"]
    assert drift is not None
    assert drift["previous_run_id"] == run1["id"]

    by_id = {n["node_id"]: n for n in drift["nodes"]}
    in1 = by_id["in1"]
    assert in1["rows_before"] == len(ROWS_A)
    assert in1["rows_after"] == len(ROWS_B)
    assert in1["rows_delta"] == len(ROWS_B) - len(ROWS_A)


async def test_drift_reports_added_and_removed_columns(client: AsyncClient) -> None:
    ds1 = await _upload(client, ROWS_A, "a.csv")
    flow = await _create_flow(client, _graph(ds1["id"]))
    await _run(client, flow["id"])

    ds2 = await _upload(client, ROWS_B, "b.csv")
    await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph(ds2["id"])})
    run2 = await _run(client, flow["id"])

    fetched = (await client.get(f"/api/runs/{run2['id']}")).json()
    in1 = {n["node_id"]: n for n in fetched["drift"]["nodes"]}["in1"]
    assert in1["columns_added"] == ["city"]
    assert in1["columns_removed"] == []

    # Shrink back: drop the city column (and age) — they should show as removed.
    ds3 = await _upload(client, [{"name": "z"}], "c.csv")
    await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph(ds3["id"])})
    run3 = await _run(client, flow["id"])

    fetched3 = (await client.get(f"/api/runs/{run3['id']}")).json()
    in1_3 = {n["node_id"]: n for n in fetched3["drift"]["nodes"]}["in1"]
    assert in1_3["columns_removed"] == ["age", "city"]
    assert in1_3["columns_added"] == []
    # run1's baseline is ignored: only the immediately preceding run (run2) counts.
    assert fetched3["drift"]["previous_run_id"] == run2["id"]


async def test_drift_reports_nodes_added_and_removed(client: AsyncClient) -> None:
    ds = await _upload(client, ROWS_A, "a.csv")
    flow = await _create_flow(client, _graph(ds["id"]))
    await _run(client, flow["id"])

    await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph_with_drop(ds["id"])})
    run2 = await _run(client, flow["id"])

    fetched2 = (await client.get(f"/api/runs/{run2['id']}")).json()
    assert fetched2["drift"]["nodes_added"] == ["drop"]
    assert fetched2["drift"]["nodes_removed"] == []

    await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph(ds["id"])})
    run3 = await _run(client, flow["id"])

    fetched3 = (await client.get(f"/api/runs/{run3['id']}")).json()
    assert fetched3["drift"]["nodes_removed"] == ["drop"]
    assert fetched3["drift"]["nodes_added"] == []


async def test_previous_run_without_results_is_not_a_baseline(client: AsyncClient) -> None:
    """A failed run that recorded no node results must not suppress the diff
    or act as a baseline — the next successful run is still a 'first'."""
    ds = await _upload(client, ROWS_A, "a.csv")
    flow = await _create_flow(client, _graph("no-such-dataset"))

    bad = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert bad["status"] == "failed"
    assert not bad["node_results"]

    await client.put(f"/api/flows/{flow['id']}", json={"graph_json": _graph(ds["id"])})
    good = await _run(client, flow["id"])

    fetched = (await client.get(f"/api/runs/{good['id']}")).json()
    assert fetched["drift"] is None


# ---------------------------------------------------------------------------
# Pure compute_node_drift unit tests
# ---------------------------------------------------------------------------


def _result(node_id: str, rows: int, columns: list[str]) -> dict[str, Any]:
    return {"node_id": node_id, "label": node_id, "rows": rows, "columns": columns}


def test_compute_drift_returns_none_without_baseline() -> None:
    results = [_result("a", 5, ["x"])]
    assert compute_node_drift(results, None) is None
    assert compute_node_drift(results, []) is None


def test_compute_drift_none_when_unchanged() -> None:
    results = [_result("a", 5, ["x", "y"])]
    assert compute_node_drift(results, results) is None


def test_compute_drift_reorder_is_not_a_schema_change() -> None:
    prev = [_result("a", 5, ["x", "y"])]
    cur = [_result("a", 5, ["y", "x"])]
    assert compute_node_drift(cur, prev) is None


def test_compute_drift_rows_delta() -> None:
    prev = [_result("a", 5, ["x"])]
    cur = [_result("a", 7, ["x"])]
    nodes, added, removed = compute_node_drift(cur, prev)
    assert added == []
    assert removed == []
    assert len(nodes) == 1
    assert nodes[0].rows_before == 5
    assert nodes[0].rows_after == 7
    assert nodes[0].rows_delta == 2
    assert nodes[0].columns_added == []
    assert nodes[0].columns_removed == []


def test_compute_drift_column_diffs() -> None:
    prev = [_result("a", 5, ["x", "y"])]
    cur = [_result("a", 5, ["x", "z"])]
    nodes, added, removed = compute_node_drift(cur, prev)
    assert nodes[0].columns_added == ["z"]
    assert nodes[0].columns_removed == ["y"]


def test_compute_drift_nodes_added_and_removed_only() -> None:
    prev = [_result("a", 5, ["x"])]
    cur = [_result("a", 5, ["x"]), _result("b", 5, ["y"])]
    nodes, added, removed = compute_node_drift(cur, prev)
    assert nodes == []
    assert added == ["b"]
    assert removed == []

    nodes2, added2, removed2 = compute_node_drift(prev, cur)
    assert nodes2 == []
    assert added2 == []
    assert removed2 == ["b"]


def test_compute_drift_missing_rows_stays_silent() -> None:
    prev = [{"node_id": "a", "label": "a", "rows": None, "columns": ["x"]}]
    cur = [{"node_id": "a", "label": "a", "rows": None, "columns": ["x"]}]
    assert compute_node_drift(cur, prev) is None
