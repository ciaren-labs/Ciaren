"""Shared fixtures for ML node tests: an isolated MLflow tracking dir and a helper
that trains a model and returns its reference frame."""

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.transformations.ml.train import MLTrainTransformation


@pytest.fixture
def ml_env(tmp_path, monkeypatch):
    """Point MLflow + the artifact dir at a per-test temp location."""
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def classification_df(n=120, seed=0):
    rng = np.random.RandomState(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": (x1 + x2 > 0).astype(int)})


@pytest.fixture
def trained_classifier(ml_env):
    """Train a small RF classifier; return (engine, model_ref_frame, train_df)."""
    engine = get_engine("pandas")
    df = classification_df()
    frame = engine.from_pandas(df)
    out, _meta = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": frame},
        {"model_type": "random_forest_classifier", "target_column": "target", "seed": 42},
    )
    return engine, out["model"], df
