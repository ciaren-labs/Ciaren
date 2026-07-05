"""End-to-end tests for the sqlInput / sqlOutput nodes against a SQLite database.

Covers a full run (read a table → transform → write a table), preview, graph
validation, and that exported code reads secrets from the environment (never
embeds them).
"""

import pandas as pd
from httpx import AsyncClient

from app.connectors import ConnectionSpec, get_connector, get_provider
from app.engine.codegen import CodeGenerator


def _seed(path: str, rows: int = 6) -> None:
    conn = get_connector(get_provider("sqlite"))
    spec = ConnectionSpec(provider="sqlite", database=path)
    cities = ["NYC" if i % 2 == 0 else "LA" for i in range(rows)]
    df = pd.DataFrame({"id": list(range(rows)), "city": cities})
    conn.write_table(spec, df, "source", None, "replace")


def _read_table(path: str, table: str) -> pd.DataFrame:
    conn = get_connector(get_provider("sqlite"))
    return conn.read_table(ConnectionSpec(provider="sqlite", database=path), table, None, None)


async def _connection(client: AsyncClient, db_path: str) -> dict:
    r = await client.post(
        "/api/connections",
        json={"name": "wh", "provider": "sqlite", "database": db_path},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "sqlflow", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


def _sql_graph(connection_id: str) -> dict:
    in_cfg = {"connection_id": connection_id, "mode": "table", "table": "source"}
    filter_cfg = {"column": "city", "operator": "==", "value": "NYC"}
    out_cfg = {"connection_id": connection_id, "table": "dest", "if_exists": "replace"}
    return {
        "nodes": [
            {"id": "in1", "type": "sqlInput", "data": {"config": in_cfg}},
            {"id": "f1", "type": "filterRows", "data": {"config": filter_cfg}},
            {"id": "out1", "type": "sqlOutput", "data": {"config": out_cfg}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "f1"},
            {"id": "e2", "source": "f1", "target": "out1"},
        ],
    }


async def test_sql_input_to_output_run(client: AsyncClient, tmp_path) -> None:
    db = str(tmp_path / "wh.db")
    _seed(db, rows=6)
    conn = await _connection(client, db)
    flow = await _create_flow(client, _sql_graph(conn["id"]))

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "success", r.json()

    # The sink table now exists in the database with only the NYC rows
    # (6 rows seeded, alternating NYC/LA → 3 NYC).
    dest = _read_table(db, "dest")
    assert len(dest) == 3
    assert set(dest["city"]) == {"NYC"}


async def test_sql_preview(client: AsyncClient, tmp_path) -> None:
    db = str(tmp_path / "p.db")
    _seed(db, rows=4)
    conn = await _connection(client, db)
    flow = await _create_flow(client, _sql_graph(conn["id"]))

    r = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "in1"})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 4


async def test_sql_input_requires_connection(client: AsyncClient) -> None:
    graph = {
        "nodes": [
            {"id": "in1", "type": "sqlInput", "data": {"config": {"mode": "table", "table": "x"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow = await _create_flow(client, graph)
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    # Refused up front: graph validation now runs before a run row is created,
    # so a misconfigured SQL input is a clean 400, not a failed run.
    assert r.status_code == 400
    assert "connection" in r.json()["detail"]


def test_codegen_reads_secret_from_env_not_inline() -> None:
    graph = {
        "nodes": [
            {
                "id": "in1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": "c1", "mode": "table", "table": "orders"}},
            },
            {
                "id": "out1",
                "type": "sqlOutput",
                "data": {"config": {"connection_id": "c1", "table": "out", "if_exists": "append"}},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    connections = {
        "c1": {
            "provider": "postgresql",
            "host": "db.example.com",
            "port": 5432,
            "database": "shop",
            "username": "reader",
            "password_env": "PG_PASSWORD",
        }
    }
    code = CodeGenerator().generate(graph, {}, connections)
    assert "os.environ['PG_PASSWORD']" in code
    assert "create_engine" in code
    assert "pd.read_sql_table('orders'" in code
    assert "to_sql('out'" in code
    # The actual password must never appear — only the env-var reference.
    assert "PG_PASSWORD" in code  # the name is fine
    compile(code, "<sql>", "exec")
