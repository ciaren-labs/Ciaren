"""Characterization tests for a documented flow-parameters risk.

Parameter substitution (``app.engine.parameters.apply_parameters``) is plain
string interpolation — it has no idea that the field it's writing into will
later be compiled as Python (``pythonTransform``), evaluated as a pandas
expression (``assertExpression`` / derive), or sent as literal SQL
(``sqlInput`` in ``query`` mode). If a flow author embeds ``{{ param }}``
inside one of those fields, a *run-time* caller who supplies that parameter's
value is effectively supplying code/query text, not a bound value.

This is intentional, accepted behavior — the same trust model as
"pythonTransform is unsandboxed" and "SQL ``read_query`` is arbitrary SQL by
design" (see SECURITY.md and docs/guide/parameters.md's Security note): Ciaren
assumes whoever can call the run/schedule API is as trusted as the flow's
author. These tests exist so a future change can't silently "fix" (or regress)
this behavior without a test failing — and so the risk has an executable,
concrete demonstration instead of just a paragraph of prose.
"""

import io

import pandas as pd
from httpx import AsyncClient

from app.connectors import ConnectionSpec, get_connector, get_provider


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "risk", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame([{"v": 1}, {"v": 2}]).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("nums.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def test_string_parameter_in_python_script_allows_statement_injection(client: AsyncClient, tmp_path) -> None:
    """A `string` parameter embedded in a pythonTransform script is spliced into
    Python source, not passed as a value — an override can close the quoted
    literal and inject additional statements."""
    ds = await _upload(client)
    graph = {
        "parameters": [{"name": "greeting", "type": "string", "default": "hi"}],
        "nodes": [
            {"id": "in0", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {
                "id": "in1",
                "type": "pythonTransform",
                "data": {"config": {"script": "df['msg'] = '{{ greeting }}'\nreturn df"}},
            },
        ],
        "edges": [{"id": "e1", "source": "in0", "target": "in1"}],
    }
    # The flow author only ever intended `greeting` to fill in a message string.
    flow = await _create_flow(client, graph)

    # A run-time caller instead closes the string literal and adds a statement.
    payload = "x'; df['pwned'] = 1; msg='"
    r = await client.post(
        f"/api/flows/{flow['id']}/preview",
        json={"node_id": "in1", "parameters": {"greeting": payload}},
    )
    assert r.status_code == 200, r.text
    assert "pwned" in r.json()["columns"], "injected statement did not execute — investigate this test"


async def test_string_parameter_in_filter_expression_allows_condition_injection(client: AsyncClient, tmp_path) -> None:
    """A parameter embedded in a `filterExpression` `expression` is spliced into
    the text handed to pandas `df.eval()`/`df.query()` — an override can widen or
    replace the intended row filter, not just supply a threshold value."""
    ds = await _upload(client)
    graph = {
        "parameters": [{"name": "threshold", "type": "string", "default": "1"}],
        "nodes": [
            {"id": "in0", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {
                "id": "in1",
                "type": "filterExpression",
                "data": {"config": {"expression": "v > {{ threshold }}"}},
            },
        ],
        "edges": [{"id": "e1", "source": "in0", "target": "in1"}],
    }
    flow = await _create_flow(client, graph)

    # Intended use: keep rows with v greater than the threshold. Only 1 of 2 rows (v in {1, 2}).
    r_default = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "in1"})
    assert r_default.status_code == 200, r_default.text
    assert r_default.json()["row_count"] == 1

    # A run-time caller instead supplies a tautology, defeating the filter entirely.
    r_injected = await client.post(
        f"/api/flows/{flow['id']}/preview",
        json={"node_id": "in1", "parameters": {"threshold": "0 or v == v"}},
    )
    assert r_injected.status_code == 200, r_injected.text
    assert r_injected.json()["row_count"] == 2, "injected condition did not widen the result set"


async def test_string_parameter_in_sql_query_allows_condition_injection(client: AsyncClient, tmp_path) -> None:
    """A `string` parameter embedded in a sqlInput `query` (mode="query") field is
    spliced into the literal SQL text sent to the database — an override can
    widen or replace the intended WHERE clause."""
    db_path = str(tmp_path / "wh.db")
    conn = get_connector(get_provider("sqlite"))
    spec = ConnectionSpec(provider="sqlite", database=db_path)
    df = pd.DataFrame({"id": [1, 2, 3], "city": ["NYC", "LA", "NYC"], "secret": ["a", "b", "c"]})
    conn.write_table(spec, df, "source", None, "replace")

    conn_resp = await client.post("/api/connections", json={"name": "wh", "provider": "sqlite", "database": db_path})
    assert conn_resp.status_code == 201, conn_resp.text
    connection_id = conn_resp.json()["id"]

    graph = {
        "parameters": [{"name": "city", "type": "string", "default": "NYC"}],
        "nodes": [
            {
                "id": "in1",
                "type": "sqlInput",
                "data": {
                    "config": {
                        "connection_id": connection_id,
                        "mode": "query",
                        "query": "SELECT * FROM source WHERE city = '{{ city }}'",
                    }
                },
            },
        ],
        "edges": [],
    }
    flow = await _create_flow(client, graph)

    # Intended use: filter to one city. Only 2 of 3 rows match "NYC".
    r_default = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "in1"})
    assert r_default.status_code == 200, r_default.text
    assert r_default.json()["row_count"] == 2

    # A run-time caller instead supplies a tautology, bypassing the filter entirely.
    r_injected = await client.post(
        f"/api/flows/{flow['id']}/preview",
        json={"node_id": "in1", "parameters": {"city": "NYC' OR '1'='1"}},
    )
    assert r_injected.status_code == 200, r_injected.text
    assert r_injected.json()["row_count"] == 3, "injected condition did not widen the result set"
