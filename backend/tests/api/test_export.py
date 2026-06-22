"""
Python code export endpoint tests.

  POST /api/flows/{flow_id}/export/python
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": None},
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
            {"id": "out1", "type": "csvOutput", "data": {"config": {"path": "clean.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


async def test_export_python_happy_path(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert "import pandas as pd" in code
    assert 'pd.read_csv("people.csv")' in code  # dataset name, not server path
    assert ".dropna()" in code
    assert ".to_csv(" in code
    compile(code, "<exported>", "exec")  # must be valid Python


async def test_export_python_missing_flow(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/export/python")
    assert r.status_code == 404


async def test_export_python_incomplete_graph_is_400(client: AsyncClient) -> None:
    ds = await _upload(client)
    # No output node -> invalid for export.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
        ],
        "edges": [],
    }
    flow = await _create_flow(client, graph)
    r = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert r.status_code == 400
