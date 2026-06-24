"""mlEvaluate: classification / regression / clustering metrics in long format."""
import numpy as np
import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.transformations.ml.evaluate import MLEvaluateTransformation

NODE = MLEvaluateTransformation()
ENGINE = get_engine("pandas")


def _metrics(df, config):
    out, meta = NODE.execute_with_metadata(ENGINE, {"in": ENGINE.from_pandas(df)}, config)
    long_df = ENGINE.to_pandas(out["out"])
    return dict(zip(long_df["metric"], long_df["value"])), meta


def test_classification_metrics():
    df = pd.DataFrame({"y": [0, 1, 1, 0, 1], "pred": [0, 1, 0, 0, 1]})
    metrics, meta = _metrics(df, {"task_type": "classification", "target_column": "y", "prediction_column": "pred"})
    assert metrics["accuracy"] == pytest.approx(0.8)
    assert "f1" in metrics and "precision" in metrics and "recall" in metrics
    assert meta.ml_metrics["accuracy"] == pytest.approx(0.8)
    assert meta.task_type == "classification"


def test_confusion_matrix_flattened():
    df = pd.DataFrame({"y": [0, 0, 1, 1], "pred": [0, 1, 1, 1]})
    metrics, _ = _metrics(
        df,
        {"task_type": "classification", "target_column": "y", "prediction_column": "pred",
         "metrics": ["accuracy", "confusion_matrix"]},
    )
    # 2x2 matrix -> 4 flattened cells
    assert metrics["cm_true0_pred0"] == 1.0
    assert metrics["cm_true1_pred1"] == 2.0


def test_roc_auc_with_proba():
    df = pd.DataFrame({
        "y": [0, 0, 1, 1],
        "pred": [0, 0, 1, 1],
        "p0": [0.9, 0.8, 0.2, 0.1],
        "p1": [0.1, 0.2, 0.8, 0.9],
    })
    metrics, _ = _metrics(
        df,
        {"task_type": "classification", "target_column": "y", "prediction_column": "pred",
         "metrics": ["roc_auc"], "proba_columns": ["p0", "p1"]},
    )
    assert metrics["roc_auc"] == pytest.approx(1.0)


def test_regression_metrics():
    rng = np.random.RandomState(0)
    y = rng.normal(size=50)
    df = pd.DataFrame({"y": y, "pred": y + rng.normal(scale=0.1, size=50)})
    metrics, _ = _metrics(df, {"task_type": "regression", "target_column": "y", "prediction_column": "pred"})
    assert metrics["r2"] > 0.9
    assert "rmse" in metrics and "mae" in metrics and "mape" in metrics


def test_clustering_metrics():
    rng = np.random.RandomState(0)
    df = pd.DataFrame({
        "x": np.concatenate([rng.normal(0, 0.2, 30), rng.normal(5, 0.2, 30)]),
        "y": np.concatenate([rng.normal(0, 0.2, 30), rng.normal(5, 0.2, 30)]),
        "cluster": [0] * 30 + [1] * 30,
    })
    metrics, meta = _metrics(df, {"task_type": "clustering", "prediction_column": "cluster"})
    assert metrics["silhouette"] > 0.5
    assert "davies_bouldin" in metrics
    assert meta.task_type == "clustering"


def test_validate_config():
    with pytest.raises(ValueError, match="task_type"):
        NODE.validate_config({"task_type": "ranking"})
    with pytest.raises(ValueError, match="target_column"):
        NODE.validate_config({"task_type": "classification", "prediction_column": "p"})
    with pytest.raises(ValueError, match="prediction_column"):
        NODE.validate_config({"task_type": "regression", "target_column": "y"})


def test_missing_columns_raise():
    df = pd.DataFrame({"y": [0, 1], "pred": [0, 1]})
    with pytest.raises(ValueError, match="not found"):
        _metrics(df, {"task_type": "classification", "target_column": "ghost", "prediction_column": "pred"})
