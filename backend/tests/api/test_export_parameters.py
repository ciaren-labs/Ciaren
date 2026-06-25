"""Export of parameterized flows: parameters render as real variables, the script
stays valid Python, and malformed specs are rejected at save time.
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame([{"v": 1}, {"v": 2}, {"v": 3}]).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("nums.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def _graph(dataset_id: str) -> dict[str, Any]:
    return {
        "parameters": [
            {"name": "keep", "type": "integer", "default": 2, "description": "rows kept"},
            {"name": "out", "type": "string", "default": "result.csv"},
        ],
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "lim", "type": "limitRows", "data": {"config": {"n": "{{ keep }}"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {"path": "{{ out }}"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "lim"},
            {"id": "e2", "source": "lim", "target": "out1"},
        ],
    }


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def test_export_renders_parameters_as_variables(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _graph(ds["id"]))

    body = (await client.post(f"/api/flows/{flow['id']}/export/python")).json()

    for script in (body["code"], body["polars"], body["polars_lazy"]):
        # The parameters block defines the variables...
        assert "# Flow parameters" in script
        assert "keep = 2  # rows kept" in script
        assert "out = 'result.csv'" in script
        # ...and the body references them rather than inlining literals.
        assert ".head(keep)" in script
        assert "(out" in script  # to_csv(out, ...) / write_csv(out)
        # Every exported script must be valid Python.
        compile(script, "<export>", "exec")


async def test_malformed_parameters_rejected_at_save(client: AsyncClient) -> None:
    # Duplicate parameter name.
    graph = {
        "parameters": [{"name": "x", "default": 1}, {"name": "x", "default": 2}],
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}],
        "edges": [],
    }
    r = await client.post("/api/flows", json={"name": "bad", "graph_json": graph})
    assert r.status_code == 400, r.text


async def test_bad_default_type_rejected_at_save(client: AsyncClient) -> None:
    graph = {
        "parameters": [{"name": "n", "type": "integer", "default": "not-a-number"}],
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}],
        "edges": [],
    }
    r = await client.post("/api/flows", json={"name": "bad", "graph_json": graph})
    assert r.status_code == 400, r.text
