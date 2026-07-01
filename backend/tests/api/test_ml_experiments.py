"""GET /api/flows/{id}/ml/experiments — lists MLflow experiments a flow logs to."""

import io

import numpy as np
import pandas as pd
from httpx import AsyncClient

from app.core.config import get_settings


def _ml_graph(dataset_id: str, experiment: str | None = None) -> dict:
    cfg = {"model_type": "logistic_regression", "target_column": "target", "seed": 1}
    if experiment:
        cfg["mlflow_experiment"] = experiment
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "tr", "type": "mlTrainClassifier", "data": {"config": cfg}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "tr"}],
    }


async def _upload(client: AsyncClient) -> dict:
    rng = np.random.RandomState(0)
    x = rng.normal(size=(60, 2))
    df = pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "target": (x[:, 0] + x[:, 1] > 0).astype(int)})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})
    return r.json()


async def test_experiments_501_when_disabled(client: AsyncClient) -> None:
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _ml_graph("x")})).json()
    r = await client.get(f"/api/flows/{flow['id']}/ml/experiments")
    assert r.status_code == 501


async def test_experiments_empty_before_any_run(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _ml_graph(ds["id"])})).json()
        # experiment not created until a run logs to it
        r = await client.get(f"/api/flows/{flow['id']}/ml/experiments")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        get_settings.cache_clear()


async def test_experiments_listed_after_run(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        graph = _ml_graph(ds["id"], experiment="my-experiment")
        flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
        run = await client.post(f"/api/flows/{flow['id']}/runs", json={})
        assert run.status_code == 201, run.text
        assert run.json()["status"] == "success", run.json()

        r = await client.get(f"/api/flows/{flow['id']}/ml/experiments")
        assert r.status_code == 200
        names = [e["name"] for e in r.json()]
        assert "my-experiment" in names
    finally:
        get_settings.cache_clear()


async def test_experiments_empty_for_non_ml_flow(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    try:
        graph = {
            "nodes": [
                {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "x"}}},
                {"id": "o", "type": "csvOutput", "data": {"config": {}}},
            ],
            "edges": [{"id": "e1", "source": "in1", "target": "o"}],
        }
        flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
        r = await client.get(f"/api/flows/{flow['id']}/ml/experiments")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        get_settings.cache_clear()
