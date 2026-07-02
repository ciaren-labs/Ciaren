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


async def test_export_includes_portable_flow_document(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert r.status_code == 200, r.text
    doc = r.json()["flow_document"]
    assert doc["format"] == "ciaren.flow/v1"
    assert doc["name"] == "f"
    assert [n["id"] for n in doc["graph_json"]["nodes"]] == ["in1", "drop", "out1"]


async def test_import_flow_strips_env_bindings(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    doc = (await client.post(f"/api/flows/{flow['id']}/export/python")).json()["flow_document"]

    # Importing recreates the structure but drops the dataset binding.
    r = await client.post("/api/flows/import", json=doc)
    assert r.status_code == 201, r.text
    imported = r.json()
    assert imported["id"] != flow["id"]
    assert imported["project_id"]  # always assigned a project
    nodes = {n["id"]: n for n in imported["graph_json"]["nodes"]}
    assert "dataset_id" not in nodes["in1"]["data"]["config"]
    assert [n["id"] for n in imported["graph_json"]["nodes"]] == ["in1", "drop", "out1"]


async def test_import_flow_honors_target_project(client: AsyncClient) -> None:
    proj = (await client.post("/api/projects", json={"name": "Imports"})).json()
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    doc = (await client.post(f"/api/flows/{flow['id']}/export/python")).json()["flow_document"]
    doc["project_id"] = proj["id"]

    r = await client.post("/api/flows/import", json=doc)
    assert r.status_code == 201, r.text
    assert r.json()["project_id"] == proj["id"]


async def test_import_flow_rejects_unknown_node_type(client: AsyncClient) -> None:
    doc = {
        "format": "ciaren.flow/v1",
        "name": "bad",
        "graph_json": {"nodes": [{"id": "x", "type": "totallyNotANode", "data": {}}], "edges": []},
    }
    r = await client.post("/api/flows/import", json=doc)
    assert r.status_code == 400, r.text
    assert "Unknown node types" in r.json()["detail"]


async def test_export_python_happy_path(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert r.status_code == 200, r.text
    body = r.json()
    code = body["code"]
    assert "import pandas as pd" in code
    assert "pd.read_csv('people.csv')" in code  # dataset name, not server path
    assert ".dropna()" in code
    assert ".to_csv(" in code
    compile(code, "<exported>", "exec")  # must be valid Python

    # The polars equivalent is generated alongside it.
    polars = body["polars"]
    assert "import polars as pl" in polars
    assert "pl.read_csv('people.csv')" in polars
    assert ".drop_nulls()" in polars
    assert ".write_csv(" in polars
    compile(polars, "<exported-polars>", "exec")

    # ...and the optimized lazy polars variant.
    polars_lazy = body["polars_lazy"]
    assert "pl.scan_csv('people.csv')" in polars_lazy
    assert ".collect().write_csv(" in polars_lazy
    compile(polars_lazy, "<exported-polars-lazy>", "exec")


async def test_export_free_intermediates_adds_del(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = _full_graph(ds["id"])
    # Fan the input out to a second sink so an intermediate actually outlives its
    # producer — on a purely linear chain variable reuse leaves nothing to free.
    graph["nodes"].append({"id": "out2", "type": "csvOutput", "data": {"config": {"path": "raw.csv"}}})
    graph["edges"].append({"id": "e3", "source": "in1", "target": "out2"})
    flow = await _create_flow(client, graph)
    r = await client.post(f"/api/flows/{flow['id']}/export/python?free_intermediates=true")
    assert r.status_code == 200, r.text
    body = r.json()
    # del appears in the materializing scripts but never in the lazy one.
    assert "del df_1" in body["code"]
    assert "del df_1" in body["polars"]
    assert "del " not in body["polars_lazy"]
    compile(body["code"], "<exported-del>", "exec")


async def test_export_linear_chain_reuses_variable(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    body = (await client.post(f"/api/flows/{flow['id']}/export/python")).json()
    # in -> dropNulls -> out is a straight line: one df_1, reassigned in place.
    assert "df_1 = df_1.dropna()" in body["code"]
    assert "df_1 = df_1.drop_nulls()" in body["polars"]
    assert "df_2" not in body["code"] and "df_2" not in body["polars"]


async def test_export_python_missing_flow(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/export/python")
    assert r.status_code == 404


def test_sql_codegen_duckdb_driver_name() -> None:
    """DuckDB nodes must emit 'duckdb:///' not fall back to the bare provider name."""
    from app.engine.sql_codegen import engine_url_expr

    expr = engine_url_expr({"provider": "duckdb", "database": "/data/warehouse.ddb"})
    assert "duckdb:///" in expr
    assert "/data/warehouse.ddb" in expr
    compile(expr, "<test>", "eval")  # must be valid Python


def test_sql_codegen_snowflake_driver_name() -> None:
    """Snowflake nodes must emit the snowflake:// driver name."""
    from app.engine.sql_codegen import engine_url_expr

    expr = engine_url_expr({"provider": "snowflake", "host": "my-account", "database": "mydb", "username": "user"})
    assert "snowflake://" in expr
    compile(expr, "<test>", "eval")


def test_sql_codegen_rejects_invalid_password_env() -> None:
    """An invalid password_env name must raise ValueError, not silently emit broken code."""
    import pytest

    from app.engine.sql_codegen import engine_url_expr

    for bad in ["1STARTS_DIGIT", "has space", "has-dash", "has$dollar"]:
        with pytest.raises(ValueError, match="password_env"):
            engine_url_expr({"provider": "postgresql", "host": "localhost", "database": "db", "password_env": bad})


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
