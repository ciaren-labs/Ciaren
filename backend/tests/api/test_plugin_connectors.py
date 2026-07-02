"""Plugin-contributed connectors through the connections API and the node
resolvers: provider listing (with form schema), validation, test, table/object
listing, and sqlInput/storageInput materialization + output push."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from app.core.exceptions import ValidationError
from app.db.models.connection import Connection
from app.plugin_api import (
    ConnectorProvider,
    ConnectorRuntime,
    ConnectorSpec,
    ConnectorTestResult,
)
from app.plugins import get_registry, reset_registry

# -- a fake in-memory "API warehouse" connector (sql-ish kind) -------------------

TABLES = {
    "users": pd.DataFrame({"id": [1, 2, 3], "name": ["ada", "bo", "cy"]}),
    "orders": pd.DataFrame({"order_id": [10, 11], "total": [9.5, 12.0]}),
}


class MemRuntime(ConnectorRuntime):
    def __init__(self) -> None:
        self.written: dict[str, pd.DataFrame] = {}
        self.seen_configs: list[dict[str, Any]] = []

    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        self.seen_configs.append(config)
        if not (config.get("options") or {}).get("base_url"):
            return ConnectorTestResult(ok=False, message="base_url missing")
        return ConnectorTestResult(ok=True, message="memdb reachable")

    def list_tables(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"name": t, "schema": None, "row_count": len(df)} for t, df in TABLES.items()]

    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        if options.get("mode") == "query":
            raise ValueError("memdb does not speak SQL")
        table = options.get("table", "")
        if table not in TABLES:
            raise ValueError(f"unknown table {table!r}")
        return TABLES[table]

    def write(self, frame: Any, config: dict[str, Any], options: dict[str, Any]) -> None:
        self.written[options.get("table", "")] = frame


class MemStorageRuntime(ConnectorRuntime):
    def __init__(self) -> None:
        self.files: dict[str, pd.DataFrame] = {"in/users.csv": TABLES["users"]}

    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        return ConnectorTestResult(ok=True)

    def list_objects(self, config: dict[str, Any], prefix: str = "") -> list[str]:
        return [k for k in self.files if k.startswith(prefix)]

    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        return self.files[options["path"]]

    def write(self, frame: Any, config: dict[str, Any], options: dict[str, Any]) -> None:
        self.files[options["path"]] = frame


MEM_SCHEMA = {
    "fields": [
        {"key": "base_url", "label": "Base URL", "type": "string", "required": True},
        {"key": "verify_tls", "type": "boolean", "default": True},
    ]
}


class _Provider(ConnectorProvider):
    def __init__(self, sql_runtime: MemRuntime, storage_runtime: MemStorageRuntime) -> None:
        self._sql = sql_runtime
        self._storage = storage_runtime

    def connectors(self) -> list[ConnectorSpec]:
        return [
            ConnectorSpec(
                id="memdb",
                label="Mem Warehouse",
                kind="api",
                provider="community.mem-connector",
                metadata={"needs_host": False, "needs_auth": False, "supports_query": False},
                config_schema=MEM_SCHEMA,
            ),
            ConnectorSpec(
                id="memstore",
                label="Mem Storage",
                kind="storage",
                provider="community.mem-connector",
            ),
        ]

    def connector_implementations(self) -> dict[str, Any]:
        return {"memdb": self._sql, "memstore": self._storage}


@pytest.fixture
def mem_connector():
    sql_runtime, storage_runtime = MemRuntime(), MemStorageRuntime()
    get_registry().register_connector_provider(_Provider(sql_runtime, storage_runtime))
    yield sql_runtime, storage_runtime
    reset_registry()


async def _create_mem_connection(client: AsyncClient, **overrides) -> dict:
    body = {"name": "mem", "provider": "memdb", "options": {"base_url": "https://api.example.com"}}
    body.update(overrides)
    r = await client.post("/api/connections", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# -- providers listing -------------------------------------------------------------


async def test_providers_include_plugin_connectors(client: AsyncClient, mem_connector):
    r = await client.get("/api/connections/providers")
    assert r.status_code == 200
    entry = next(p for p in r.json() if p["name"] == "memdb")
    assert entry["plugin"] is True
    assert entry["plugin_id"] == "community.mem-connector"
    assert entry["label"] == "Mem Warehouse"
    assert entry["config_schema"] == MEM_SCHEMA
    # Core providers are untouched (no plugin flag).
    core = next(p for p in r.json() if p["name"] == "postgresql")
    assert "plugin" not in core


# -- CRUD + validation --------------------------------------------------------------


async def test_create_plugin_connection_and_kind(client: AsyncClient, mem_connector):
    created = await _create_mem_connection(client)
    assert created["provider"] == "memdb"
    assert created["connection_type"] == "api"

    storage = await client.post("/api/connections", json={"name": "ms", "provider": "memstore"})
    assert storage.status_code == 201
    assert storage.json()["connection_type"] == "storage"


async def test_create_requires_schema_required_fields(client: AsyncClient, mem_connector):
    r = await client.post("/api/connections", json={"name": "bad", "provider": "memdb"})
    assert r.status_code == 400
    assert "Base URL" in r.json()["detail"]


async def test_unknown_provider_still_rejected(client: AsyncClient, mem_connector):
    r = await client.post("/api/connections", json={"name": "x", "provider": "no-such"})
    assert r.status_code == 400


# -- test + listing -----------------------------------------------------------------


async def test_test_config_routes_to_plugin_runtime(client: AsyncClient, mem_connector):
    r = await client.post(
        "/api/connections/test-config",
        json={"name": "mem", "provider": "memdb", "options": {"base_url": "https://api.example.com"}},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True, "message": "memdb reachable"}


async def test_saved_connection_test_and_tables(client: AsyncClient, mem_connector):
    created = await _create_mem_connection(client)
    t = await client.post(f"/api/connections/{created['id']}/test")
    assert t.status_code == 200 and t.json()["ok"] is True

    tables = await client.get(f"/api/connections/{created['id']}/tables")
    assert tables.status_code == 200
    assert {t["name"] for t in tables.json()} == {"users", "orders"}


async def test_storage_plugin_lists_objects(client: AsyncClient, mem_connector):
    created = await client.post("/api/connections", json={"name": "ms", "provider": "memstore"})
    objects = await client.get(f"/api/connections/{created.json()['id']}/objects")
    assert objects.status_code == 200
    assert objects.json() == ["in/users.csv"]


async def test_plugin_connector_gone_after_registry_reset(client: AsyncClient, mem_connector):
    created = await _create_mem_connection(client)
    reset_registry()
    # The provider no longer exists, so testing the saved connection fails cleanly.
    t = await client.post(f"/api/connections/{created['id']}/test")
    assert t.status_code == 400


# -- node resolvers ------------------------------------------------------------------


def _conn_row(provider: str, options: dict[str, Any] | None = None) -> Connection:
    return Connection(name=f"c-{provider}", provider=provider, options_json=options or {})


async def test_sql_resolver_materializes_plugin_read(db_session, tmp_path, mem_connector):
    from app.services.sql_resolver import materialize_sql_inputs

    conn = _conn_row("memdb", {"base_url": "https://api.example.com"})
    db_session.add(conn)
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "sq1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": conn.id, "mode": "table", "table": "users"}},
            }
        ],
        "edges": [],
    }
    paths = await materialize_sql_inputs(db_session, graph, tmp_path)
    df = pd.read_parquet(paths["sq1"])
    assert list(df["name"]) == ["ada", "bo", "cy"]

    # limit bounds preview reads even when the runtime ignores it.
    limited = await materialize_sql_inputs(db_session, graph, tmp_path, limit=2)
    assert len(pd.read_parquet(limited["sq1"])) == 2


async def test_sql_resolver_pushes_plugin_write(db_session, tmp_path, mem_connector):
    sql_runtime, _ = mem_connector
    from app.services.sql_resolver import push_sql_outputs

    conn = _conn_row("memdb", {"base_url": "https://api.example.com"})
    db_session.add(conn)
    await db_session.commit()

    out = tmp_path / "result.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(out, index=False)
    graph = {
        "nodes": [
            {
                "id": "so1",
                "type": "sqlOutput",
                "data": {"config": {"connection_id": conn.id, "table": "sink"}},
            }
        ],
        "edges": [],
    }
    written = await push_sql_outputs(db_session, graph, {"so1": out})
    assert written == 1
    assert list(sql_runtime.written["sink"]["a"]) == [1, 2]


async def test_storage_resolver_reads_plugin_files(db_session, tmp_path, mem_connector):
    from app.services.storage_resolver import materialize_storage_inputs

    conn = _conn_row("memstore")
    db_session.add(conn)
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "st1",
                "type": "storageInput",
                "data": {"config": {"connection_id": conn.id, "path": "in/users.csv", "format": "csv"}},
            }
        ],
        "edges": [],
    }
    paths = await materialize_storage_inputs(db_session, graph, tmp_path)
    assert list(pd.read_parquet(paths["st1"])["id"]) == [1, 2, 3]


async def test_sql_nodes_reject_plugin_storage_connection(db_session, tmp_path, mem_connector):
    from app.services.sql_resolver import materialize_sql_inputs

    conn = _conn_row("memstore")
    db_session.add(conn)
    await db_session.commit()

    graph = {
        "nodes": [
            {
                "id": "sq1",
                "type": "sqlInput",
                "data": {"config": {"connection_id": conn.id, "mode": "table", "table": "users"}},
            }
        ],
        "edges": [],
    }
    with pytest.raises(ValidationError, match="not a database"):
        await materialize_sql_inputs(db_session, graph, tmp_path)
