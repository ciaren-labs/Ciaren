"""ML run endpoints: GET /api/runs/{id}/ml/metrics and POST .../ml/register."""
import numpy as np
import pandas as pd
from httpx import AsyncClient

from app.core.config import get_settings
from app.db.models.flow import Flow
from app.db.models.run import FlowRun


async def _flow(db_session) -> str:
    flow = Flow(name="f", graph_json={"nodes": [], "edges": []})
    db_session.add(flow)
    await db_session.flush()
    return flow.id


async def _run_with_results(db_session, node_results: list[dict]) -> str:
    flow_id = await _flow(db_session)
    run = FlowRun(flow_id=flow_id, engine="pandas", status="success", node_results_json=node_results)
    db_session.add(run)
    await db_session.commit()
    return run.id


# -- metrics ----------------------------------------------------------------


async def test_metrics_returns_ml_nodes(client: AsyncClient, db_session) -> None:
    run_id = await _run_with_results(db_session, [
        {"node_id": "in1", "type": "csvInput", "status": "success"},  # no ML fields
        {"node_id": "tr", "type": "mlTrain", "label": "Train", "status": "success",
         "ml_metrics": {"train_accuracy": 0.9}, "model_uri": "models:/m-abc",
         "task_type": "classification", "cv_scores": [0.8, 0.9], "mlflow_run_id": "r1"},
    ])
    r = await client.get(f"/api/runs/{run_id}/ml/metrics")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "tr"
    assert data[0]["ml_metrics"]["train_accuracy"] == 0.9
    assert data[0]["model_uri"] == "models:/m-abc"


async def test_metrics_empty_for_non_ml_run(client: AsyncClient, db_session) -> None:
    run_id = await _run_with_results(db_session, [
        {"node_id": "in1", "type": "csvInput", "status": "success"},
        {"node_id": "drop", "type": "dropNulls", "status": "success"},
    ])
    r = await client.get(f"/api/runs/{run_id}/ml/metrics")
    assert r.status_code == 200
    assert r.json() == []


async def test_metrics_404_for_unknown_run(client: AsyncClient) -> None:
    r = await client.get("/api/runs/nope/ml/metrics")
    assert r.status_code == 404


# -- register ---------------------------------------------------------------


async def test_register_501_when_ml_disabled(client: AsyncClient, db_session) -> None:
    run_id = await _run_with_results(db_session, [
        {"node_id": "tr", "type": "mlTrain", "status": "success", "model_uri": "models:/m-abc"},
    ])
    r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "m"})
    assert r.status_code == 501


async def test_register_400_when_no_model(client: AsyncClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        run_id = await _run_with_results(db_session, [
            {"node_id": "drop", "type": "dropNulls", "status": "success"},
        ])
        r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "m"})
        assert r.status_code == 400
        assert "no trained model" in r.json()["detail"]
    finally:
        get_settings.cache_clear()


async def test_register_validation_empty_name(client: AsyncClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        run_id = await _run_with_results(db_session, [
            {"node_id": "tr", "type": "mlTrain", "status": "success", "model_uri": "models:/m-abc"},
        ])
        r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": ""})
        assert r.status_code == 422  # schema min_length
    finally:
        get_settings.cache_clear()


async def test_register_happy_path(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    # Train a real model so we have a resolvable MLflow model_uri.
    monkeypatch.setenv("FLOWFRAME_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("FLOWFRAME_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        from app.engine.backends import get_engine
        from app.engine.transformations.ml.train import MLTrainTransformation

        engine = get_engine("pandas")
        rng = np.random.RandomState(0)
        x = rng.normal(size=(60, 2))
        df = pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "target": (x[:, 0] + x[:, 1] > 0).astype(int)})
        _, meta = MLTrainTransformation().execute_with_metadata(
            engine, {"in": engine.from_pandas(df)},
            {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
        )
        run_id = await _run_with_results(db_session, [
            {"node_id": "tr", "type": "mlTrain", "status": "success",
             "model_uri": meta.model_uri, "task_type": "classification"},
        ])
        r = await client.post(
            f"/api/runs/{run_id}/ml/register", json={"model_name": "churn-model", "stage": "Staging"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["model_name"] == "churn-model"
        assert str(body["version"]) == "1"
        assert body["alias"] == "staging"
    finally:
        get_settings.cache_clear()
