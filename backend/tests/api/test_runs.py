"""
Flow run endpoint tests.

  POST /api/flows/{flow_id}/runs
  GET  /api/runs/{run_id}
"""

import io
from pathlib import Path
from typing import Any

import pandas as pd
from httpx import AsyncClient

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": None},
    {"name": "Charlie", "age": 35},
]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("people.csv", buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


def _full_graph(dataset_id: str) -> dict:
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


async def test_run_flow_success(client: AsyncClient, tmp_path: Path) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success"
    assert run["output_location"] is not None
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    # output_location must be relative, never an absolute server path
    assert not Path(run["output_location"]).is_absolute()

    # The written output should contain only the 2 non-null rows.
    out_file = tmp_path / "outputs" / run["output_location"]
    assert out_file.exists()
    assert len(pd.read_csv(out_file)) == 2


async def test_run_flow_records_failure(client: AsyncClient) -> None:
    ds = await _upload(client)
    # Reference a column that doesn't exist -> execution error captured on the run.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropColumns", "data": {"config": {"columns": ["ghost"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }
    flow = await _create_flow(client, graph)
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "failed"
    assert run["error_message"]


async def test_run_flow_missing_flow_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/runs", json={})
    assert r.status_code == 404


async def test_get_run(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    created = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    r = await client.get(f"/api/runs/{created['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == created["id"]
    assert r.json()["status"] == "success"


async def test_get_run_missing_is_404(client: AsyncClient) -> None:
    r = await client.get("/api/runs/nope")
    assert r.status_code == 404
