"""Deleting a dataset that a Production-aliased model was trained on returns 409
(plan §8), overridable with ?force=true. Relies on mlTrain's reproducibility tags."""

import io

import numpy as np
import pandas as pd
from httpx import AsyncClient

from app.core.config import get_settings


async def _upload(client: AsyncClient) -> dict:
    rng = np.random.RandomState(0)
    x = rng.normal(size=(80, 2))
    df = pd.DataFrame({"x1": x[:, 0], "x2": x[:, 1], "target": (x[:, 0] + x[:, 1] > 0).astype(int)})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("d.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _train_run(client: AsyncClient, dataset_id: str) -> str:
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "logistic_regression", "target_column": "target", "seed": 1}},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "tr"}],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()
    run = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert run.status_code == 201, run.text
    assert run.json()["status"] == "success", run.json()
    return run.json()["id"]


async def test_delete_blocked_by_production_model(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        run_id = await _train_run(client, ds["id"])
        reg = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "churn", "stage": "Production"})
        assert reg.status_code == 200, reg.text

        # delete is refused while a Production model depends on the dataset
        blocked = await client.delete(f"/api/datasets/{ds['id']}")
        assert blocked.status_code == 409
        assert "Production model" in blocked.json()["detail"]

        # force overrides
        forced = await client.delete(f"/api/datasets/{ds['id']}", params={"force": True})
        assert forced.status_code == 204
    finally:
        get_settings.cache_clear()


async def test_delete_allowed_when_not_production(client: AsyncClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIAREN_ML_ENABLED", "true")
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    get_settings.cache_clear()
    try:
        ds = await _upload(client)
        run_id = await _train_run(client, ds["id"])
        # register WITHOUT a Production alias
        reg = await client.post(f"/api/runs/{run_id}/ml/register", json={"model_name": "churn2"})
        assert reg.status_code == 200, reg.text

        ok = await client.delete(f"/api/datasets/{ds['id']}")
        assert ok.status_code == 204
    finally:
        get_settings.cache_clear()


async def test_delete_not_guarded_when_ml_disabled(client: AsyncClient) -> None:
    # ML disabled (default in tests): the guard is a no-op, delete works normally.
    ds = await _upload(client)
    r = await client.delete(f"/api/datasets/{ds['id']}")
    assert r.status_code == 204
