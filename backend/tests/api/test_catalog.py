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
    assert "fileInput" in by_id
    assert by_id["fileInput"]["inputs"] == []
    assert by_id["fileInput"]["default_config"] == {"dataset_id": "", "dataset_version": None, "format": "csv"}
    assert "csvInput" in by_id
    assert "csvOutput" in by_id
    assert by_id["csvOutput"]["outputs"] == []


async def test_catalog_nodes_hides_ml_when_disabled(client):
    # The client fixture pins ML off.
    resp = await client.get("/api/catalog/nodes")
    ids = {n["id"] for n in resp.json()}
    assert "mlTrainClassifier" not in ids
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


async def test_catalog_exporters(client):
    resp = await client.get("/api/catalog/exporters")
    assert resp.status_code == 200
    by_id = {e["id"]: e for e in resp.json()}
    # The three built-in code generators are exposed.
    assert "python" in by_id
    assert by_id["python"]["format"] == "python"
    assert by_id["python"]["file_extension"] == ".py"
    assert "polars" in by_id
    assert "polars-lazy" in by_id
    assert "exporter.python" in by_id["python"]["capabilities"]


async def test_catalog_categories_ordered(client):
    resp = await client.get("/api/catalog/categories")
    assert resp.status_code == 200
    cats = resp.json()
    ids = [c["id"] for c in cats]
    assert ids == ["input", "clean", "columns", "reshape", "analytics", "quality", "chart", "ml", "output"]
    assert {"id": "input", "label": "Inputs"} in cats


@pytest.mark.usefixtures("db_session")
async def test_catalog_nodes_shows_ml_when_enabled(client, monkeypatch):
    """With the ML extension ready, ML nodes appear in the catalog."""
    from app.ml.availability import ml_core_available

    if not ml_core_available():
        pytest.skip("core ML dependencies unavailable")

    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        resp = await client.get("/api/catalog/nodes")
        by_id = {n["id"]: n for n in resp.json()}
        assert "mlTrainClassifier" in by_id
        assert by_id["mlTrainClassifier"]["requires_ml"] is True
        # mlTrain emits a model output and is a model sink.
        assert any(p["type"] == "model" for p in by_id["mlTrainClassifier"]["outputs"])
        assert by_id["mlTrainClassifier"]["is_model_sink"] is True
    finally:
        get_settings.cache_clear()
