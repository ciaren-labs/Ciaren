"""ML feature gating at the API layer: the transformations list hides ML nodes
unless ML is enabled; ?category filters; previewing an ML node while disabled 501s."""

import io

import pandas as pd
from httpx import AsyncClient

from app.core.config import get_settings


def _enable_ml(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()


# -- disabled (default in tests) --------------------------------------------


async def test_default_list_excludes_ml_when_disabled(client: AsyncClient) -> None:
    types = (await client.get("/api/transformations")).json()
    assert "dropNulls" in types
    assert "mlTrainClassifier" not in types
    assert "trainTestSplit" not in types


async def test_category_ml_empty_when_disabled(client: AsyncClient) -> None:
    r = await client.get("/api/transformations", params={"category": "ml"})
    assert r.status_code == 200
    assert r.json() == []


async def test_category_etl_excludes_ml(client: AsyncClient) -> None:
    types = (await client.get("/api/transformations", params={"category": "etl"})).json()
    assert "dropNulls" in types
    assert "mlTrainClassifier" not in types


async def test_preview_ml_node_disabled_returns_501(client: AsyncClient) -> None:
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "trainTestSplit", "dataset_id": "x", "config": {"seed": 1}},
    )
    assert r.status_code == 501
    assert "ML support is not enabled" in r.json()["detail"]


async def test_invalid_category_rejected(client: AsyncClient) -> None:
    r = await client.get("/api/transformations", params={"category": "bogus"})
    assert r.status_code == 422


# -- enabled ----------------------------------------------------------------


async def test_default_list_includes_ml_when_enabled(client: AsyncClient, monkeypatch) -> None:
    _enable_ml(monkeypatch)
    try:
        types = (await client.get("/api/transformations")).json()
        assert "mlTrainClassifier" in types
        assert "dropNulls" in types
    finally:
        get_settings.cache_clear()


async def test_category_ml_lists_ml_nodes_when_enabled(client: AsyncClient, monkeypatch) -> None:
    _enable_ml(monkeypatch)
    try:
        ml = (await client.get("/api/transformations", params={"category": "ml"})).json()
        assert {"trainTestSplit", "mlTrainClassifier", "mlPredict", "mlEvaluate"}.issubset(set(ml))
        assert "dropNulls" not in ml
    finally:
        get_settings.cache_clear()


async def test_preview_ml_node_runs_schema_validation(client: AsyncClient, monkeypatch) -> None:
    # With ML enabled, previewing an ML node runs its data-aware validation against
    # the real dataset schema, so a bad column is a clean 400 (not a 500 from execute).
    _enable_ml(monkeypatch)
    try:
        buf = io.BytesIO()
        pd.DataFrame({"x": list(range(20)), "y": [0, 1] * 10}).to_csv(buf, index=False)
        ds = (await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})).json()
        r = await client.post(
            "/api/transformations/preview",
            json={
                "type": "trainTestSplit",
                "dataset_id": ds["id"],
                "config": {"seed": 1, "stratify_column": "missing"},
            },
        )
        assert r.status_code == 400, r.text
        assert "stratify column 'missing'" in r.json()["detail"]
    finally:
        get_settings.cache_clear()


async def test_running_an_ml_flow_is_blocked_when_disabled(client: AsyncClient) -> None:
    # ML disabled (default in tests). A crafted graph with an ML node must not run.
    buf = io.BytesIO()
    pd.DataFrame({"x": [1, 2, 3], "y": [0, 1, 0]}).to_csv(buf, index=False)
    ds = (await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})).json()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "logistic_regression", "target_column": "y", "seed": 1}},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "tr"}],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 501
    assert "ML support is not enabled" in r.json()["detail"]
