"""API tests for the backend-fed node/connector catalog."""

import pytest

from app.core.config import get_settings


async def test_catalog_nodes_returns_specs(client):
    resp = await client.get("/api/catalog/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    by_id = {n["id"]: n for n in nodes}
    # Core nodes present with their handle topology and metadata.
    assert "filterRows" in by_id
    flt = by_id["filterRows"]
    assert flt["category"] == "clean"
    assert flt["label"] == "Filter Rows"
    assert [p["id"] for p in flt["inputs"]] == ["in"]
    assert [p["id"] for p in flt["outputs"]] == ["out"]
    assert flt["default_config"] == {"column": "", "operator": "==", "value": ""}
    # I/O nodes present.
    assert "csvInput" in by_id
    assert by_id["csvInput"]["inputs"] == []
    assert "csvOutput" in by_id
    assert by_id["csvOutput"]["outputs"] == []


async def test_catalog_nodes_hides_ml_when_disabled(client):
    # The client fixture pins ML off.
    resp = await client.get("/api/catalog/nodes")
    ids = {n["id"] for n in resp.json()}
    assert "mlTrain" not in ids
    assert all(n["requires_ml"] is False for n in resp.json())


async def test_catalog_nodes_category_filter(client):
    resp = await client.get("/api/catalog/nodes", params={"category": "quality"})
    nodes = resp.json()
    assert nodes, "expected at least one quality node"
    assert {n["category"] for n in nodes} == {"quality"}
    ids = {n["id"] for n in nodes}
    assert "assertNotNull" in ids


async def test_catalog_connectors(client):
    resp = await client.get("/api/catalog/connectors")
    assert resp.status_code == 200
    by_id = {c["id"]: c for c in resp.json()}
    assert "postgresql" in by_id
    assert by_id["postgresql"]["kind"] == "sql"
    assert by_id["postgresql"]["metadata"]["default_port"] == 5432
    assert "connector.sql" in by_id["postgresql"]["capabilities"]


async def test_catalog_categories_ordered(client):
    resp = await client.get("/api/catalog/categories")
    assert resp.status_code == 200
    cats = resp.json()
    ids = [c["id"] for c in cats]
    assert ids == ["input", "clean", "columns", "reshape", "analytics", "quality", "ml", "output"]
    assert {"id": "input", "label": "Inputs"} in cats


@pytest.mark.usefixtures("db_session")
async def test_catalog_nodes_shows_ml_when_enabled(client, monkeypatch):
    """With the ML extension ready, ML nodes appear in the catalog."""
    from app.ml.availability import ml_core_available

    if not ml_core_available():
        pytest.skip("[ml] extra not installed")

    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        resp = await client.get("/api/catalog/nodes")
        by_id = {n["id"]: n for n in resp.json()}
        assert "mlTrain" in by_id
        assert by_id["mlTrain"]["requires_ml"] is True
        # mlTrain emits a model output and is a model sink.
        assert any(p["type"] == "model" for p in by_id["mlTrain"]["outputs"])
        assert by_id["mlTrain"]["is_model_sink"] is True
    finally:
        get_settings.cache_clear()
