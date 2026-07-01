"""ML run endpoints: GET /api/runs/{id}/ml/metrics and POST .../ml/register."""

import numpy as np
import pandas as pd
from httpx import AsyncClient

from app.core.config import get_settings
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.services.project_service import ProjectService


async def _flow(db_session) -> str:
    pid = (await ProjectService(db_session).ensure_default()).id
    flow = Flow(name="f", project_id=pid, graph_json={"nodes": [], "edges": []})
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
    run_id = await _run_with_results(
        db_session,
        [
            {"node_id": "in1", "type": "csvInput", "status": "success"},  # no ML fields
            {
                "node_id": "tr",
                "type": "mlTrainClassifier",
                "label": "Train",
                "status": "success",
                "ml_metrics": {"train_accuracy": 0.9},
                "model_uri": "models:/m-abc",
                "task_type": "classification",
                "cv_scores": [0.8, 0.9],
                "mlflow_run_id": "r1",
            },
        ],
    )
    r = await client.get(f"/api/runs/{run_id}/ml/metrics")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["node_id"] == "tr"
    assert data[0]["ml_metrics"]["train_accuracy"] == 0.9
    assert data[0]["model_uri"] == "models:/m-abc"


async def test_metrics_empty_for_non_ml_run(client: AsyncClient, db_session) -> None:
    run_id = await _run_with_results(
        db_session,
        [
            {"node_id": "in1", "type": "csvInput", "status": "success"},
            {"node_id": "drop", "type": "dropNulls", "status": "success"},
        ],
    )
    r = await client.get(f"/api/runs/{run_id}/ml/metrics")
    assert r.status_code == 200
    assert r.json() == []


async def test_metrics_404_for_unknown_run(client: AsyncClient) -> None:
    r = await client.get("/api/runs/nope/ml/metrics")
    assert r.status_code == 404


# -- register ---------------------------------------------------------------


async def test_register_501_when_ml_disabled(client: AsyncClient, db_session) -> None:
    run_id = await _run_with_results(
        db_session,
        [
            {"node_id": "tr", "type": "mlTrainClassifier", "status": "success", "model_uri": "models:/m-abc"},
        ],
    )
    r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "m"})
    assert r.status_code == 501


async def test_register_400_when_no_model(client: AsyncClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        run_id = await _run_with_results(
            db_session,
            [
                {"node_id": "drop", "type": "dropNulls", "status": "success"},
            ],
        )
        r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "m"})
        assert r.status_code == 400
        assert "no trained model" in r.json()["detail"]
    finally:
        get_settings.cache_clear()


async def test_register_validation_empty_name(client: AsyncClient, db_session, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        run_id = await _run_with_results(
            db_session,
            [
                {"node_id": "tr", "type": "mlTrainClassifier", "status": "success", "model_uri": "models:/m-abc"},
            ],
        )
        r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": ""})
        assert r.status_code == 422  # schema min_length
    finally:
        get_settings.cache_clear()


async def _train_register(db_session, tmp_path, name: str = "iris-model") -> dict:
    """Train a real model (with Ciaren lineage tags) and register it; returns
    the register response. Caller must have ML enabled + tracking URI set."""
    from app.engine.backends import get_engine
    from app.engine.run_context import run_context
    from app.engine.transformations.ml.train import MLTrainTransformation

    engine = get_engine("pandas")
    rng = np.random.RandomState(0)
    x = rng.normal(size=(80, 2))
    df = pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "target": (x[:, 0] + x[:, 1] > 0).astype(int)})
    with run_context(flow_id="flow-123", run_id="run-456", dataset_ids=["ds-789"]):
        _, meta = MLTrainTransformation().execute_with_metadata(
            engine,
            {"in": engine.from_pandas(df)},
            {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
        )
    run_id = await _run_with_results(
        db_session,
        [
            {
                "node_id": "tr",
                "type": "mlTrainClassifier",
                "status": "success",
                "model_uri": meta.model_uri,
                "task_type": "classification",
            },
        ],
    )
    from app.services.ml_service import MLService

    return await MLService(db_session).register_model(run_id, name)


# -- registry & experiments (ML Models page) --------------------------------


async def test_registered_models_listing(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        await _train_register(db_session, tmp_path, name="iris-model")
        r = await client.get("/api/ml/models")
        assert r.status_code == 200, r.text
        models = {m["name"]: m for m in r.json()}
        assert "iris-model" in models
        v = models["iris-model"]["versions"][0]
        assert v["version"] == "1"
        assert "train_accuracy" in v["metrics"]
        # Ciaren lineage threaded through MLflow tags.
        assert v["lineage"]["flow_id"] == "flow-123"
        assert v["lineage"]["run_id"] == "run-456"
        assert v["lineage"]["dataset_ids"] == ["ds-789"]
    finally:
        get_settings.cache_clear()


async def test_experiments_and_runs_listing(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        await _train_register(db_session, tmp_path)
        exps = (await client.get("/api/ml/experiments")).json()
        assert any(e["name"] == "ciaren" for e in exps)
        exp_id = next(e["experiment_id"] for e in exps if e["name"] == "ciaren")
        runs = (await client.get(f"/api/ml/experiments/{exp_id}/runs")).json()
        assert runs
        assert "train_accuracy" in runs[0]["metrics"]
        assert runs[0]["params"].get("model_type") == "logistic_regression"
    finally:
        get_settings.cache_clear()


async def test_models_501_when_ml_disabled(client: AsyncClient) -> None:
    r = await client.get("/api/ml/models")
    assert r.status_code == 501
    r2 = await client.get("/api/ml/experiments")
    assert r2.status_code == 501


async def test_set_and_clear_model_alias(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        await _train_register(db_session, tmp_path, name="alias-model")
        # Set an alias on version 1.
        r = await client.post("/api/ml/models/alias-model/alias", json={"alias": "Staging", "version": "1"})
        assert r.status_code == 200, r.text
        assert r.json()["alias"] == "staging"
        models = {m["name"]: m for m in (await client.get("/api/ml/models")).json()}
        assert models["alias-model"]["aliases"].get("staging") == "1"
        # Clear it.
        r2 = await client.delete("/api/ml/models/alias-model/alias/staging")
        assert r2.status_code == 200
        models2 = {m["name"]: m for m in (await client.get("/api/ml/models")).json()}
        assert "staging" not in models2["alias-model"]["aliases"]
    finally:
        get_settings.cache_clear()


async def test_register_happy_path(client: AsyncClient, db_session, tmp_path, monkeypatch) -> None:
    # Train a real model so we have a resolvable MLflow model_uri.
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    get_settings.cache_clear()
    try:
        from app.engine.backends import get_engine
        from app.engine.transformations.ml.train import MLTrainTransformation

        engine = get_engine("pandas")
        rng = np.random.RandomState(0)
        x = rng.normal(size=(60, 2))
        df = pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "target": (x[:, 0] + x[:, 1] > 0).astype(int)})
        _, meta = MLTrainTransformation().execute_with_metadata(
            engine,
            {"in": engine.from_pandas(df)},
            {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
        )
        run_id = await _run_with_results(
            db_session,
            [
                {
                    "node_id": "tr",
                    "type": "mlTrainClassifier",
                    "status": "success",
                    "model_uri": meta.model_uri,
                    "task_type": "classification",
                },
            ],
        )
        r = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "churn-model", "stage": "Staging"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["model_name"] == "churn-model"
        assert str(body["version"]) == "1"
        assert body["alias"] == "staging"
    finally:
        get_settings.cache_clear()
