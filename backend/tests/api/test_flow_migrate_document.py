"""``POST /api/flows/migrate-document`` — the standalone, non-persisting
file-to-file migration utility backing the frontend's "migrate a flow file"
tool and its import-time outdated-file warning."""

import pytest
from httpx import AsyncClient

from app.flow_schema import CURRENT_SCHEMA_VERSION, clear_migrations, register_migration


@pytest.fixture
def _clean_migration_registry():
    clear_migrations()
    yield
    clear_migrations()


async def test_legacy_already_current_document_is_not_flagged_migrated(client: AsyncClient) -> None:
    doc = {
        "format": "ciaren.flow/v1",
        "name": "x",
        "graph_json": {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []},
    }
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["migrated"] is False
    assert body["from_version"] == CURRENT_SCHEMA_VERSION
    assert body["to_version"] == CURRENT_SCHEMA_VERSION
    # legacy input is upgraded to the versioned envelope in the response.
    assert body["document"]["schemaVersion"] == CURRENT_SCHEMA_VERSION
    assert body["document"]["project"]["name"] == "x"
    assert body["document"]["graph"]["nodes"][0]["id"] == "in1"


async def test_older_document_is_migrated(client: AsyncClient, _clean_migration_registry: None) -> None:
    register_migration("0.9.0", CURRENT_SCHEMA_VERSION, lambda d: {**d, "marker": True})
    doc = {
        "schemaVersion": "0.9.0",
        "project": {"name": "old"},
        "graph": {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []},
    }
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["migrated"] is True
    assert body["from_version"] == "0.9.0"
    assert body["to_version"] == CURRENT_SCHEMA_VERSION


async def test_structurally_invalid_graph_is_400(client: AsyncClient) -> None:
    doc = {
        "project": {"name": "x"},
        "graph": {
            "nodes": [{"id": "dup", "type": "csvInput"}, {"id": "dup", "type": "csvOutput"}],
            "edges": [],
        },
    }
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 400, r.text
    assert "duplicate" in r.json()["detail"].lower()


async def test_dangling_edge_is_400(client: AsyncClient) -> None:
    doc = {
        "project": {"name": "x"},
        "graph": {
            "nodes": [{"id": "in1", "type": "csvInput"}],
            "edges": [{"source": "in1", "target": "does-not-exist"}],
        },
    }
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 400, r.text
    assert "unknown node" in r.json()["detail"].lower()


async def test_malformed_shape_is_400(client: AsyncClient) -> None:
    # Non-legacy shape (has "graph", no "graph_json") but missing "project" entirely.
    doc = {"graph": {"nodes": [{"id": "in1", "type": "csvInput"}], "edges": []}}
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 400, r.text


async def test_migrate_document_does_not_persist_a_flow(client: AsyncClient) -> None:
    before = await client.get("/api/flows")
    assert before.status_code == 200
    count_before = len(before.json())

    doc = {
        "format": "ciaren.flow/v1",
        "name": "x",
        "graph_json": {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []},
    }
    r = await client.post("/api/flows/migrate-document", json={"document": doc})
    assert r.status_code == 200, r.text

    after = await client.get("/api/flows")
    assert len(after.json()) == count_before
