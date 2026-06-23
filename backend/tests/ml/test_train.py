"""mlTrain: training across tasks, MLflow logging, CV, leakage detection, the
guardrail limits, and reproducibility. MLflow is pointed at a temp dir."""
import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.transformations.ml.base import MLSchema
from app.engine.transformations.ml.train import MLTrainTransformation

NODE = MLTrainTransformation()


@pytest.fixture
def ml_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOWFRAME_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("FLOWFRAME_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _classification_df(n=120):
    rng = np.random.RandomState(0)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = (x1 + x2 > 0).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": y})


def _regression_df(n=120):
    rng = np.random.RandomState(1)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 3 * x1 - 2 * x2 + rng.normal(scale=0.1, size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": y})


def _train(df, config, engine_name="pandas"):
    engine = get_engine(engine_name)
    frame = engine.from_pandas(df)
    out, meta = NODE.execute_with_metadata(engine, {"in": frame}, config)
    return engine, out, meta


# -- happy paths ------------------------------------------------------------


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_classification_trains_and_logs(ml_env, engine_name):
    engine, out, meta = _train(
        _classification_df(),
        {"model_type": "random_forest_classifier", "target_column": "target", "seed": 42},
        engine_name,
    )
    assert set(out) == {"out", "model"}
    assert meta.task_type == "classification"
    # MLflow 3 returns a logged-model URI (models:/m-...); older returns runs:/...
    assert meta.model_uri and meta.model_uri.startswith(("models:/", "runs:/"))
    assert meta.mlflow_run_id
    assert "train_accuracy" in meta.ml_metrics
    # model reference frame carries the URI downstream.
    model_ref = engine.to_pandas(out["model"])
    assert model_ref.loc[0, "model_uri"] == meta.model_uri
    # passthrough frame is unchanged row-count.
    assert engine.row_count(out["out"]) == 120


def test_regression_trains(ml_env):
    _, _, meta = _train(
        _regression_df(),
        {"model_type": "linear_regression", "target_column": "target", "seed": 1},
    )
    assert meta.task_type == "regression"
    assert meta.ml_metrics["train_r2"] > 0.9  # strong linear signal


def test_cross_validation_records_scores(ml_env):
    _, _, meta = _train(
        _classification_df(),
        {"model_type": "logistic_regression", "target_column": "target",
         "seed": 3, "cross_validate": True, "cv_folds": 4},
    )
    assert meta.cv_scores is not None and len(meta.cv_scores) == 4
    assert "cv_mean" in meta.ml_metrics


def test_xgboost_classifier_trains(ml_env):
    _, _, meta = _train(
        _classification_df(),
        {"model_type": "xgboost_classifier", "target_column": "target", "seed": 0},
    )
    assert meta.model_uri


def test_preprocessing_handles_categorical(ml_env):
    df = _classification_df()
    df["cat"] = (["a", "b", "c"] * 40)[: len(df)]
    _, _, meta = _train(
        df,
        {"model_type": "logistic_regression", "target_column": "target", "seed": 5,
         "feature_columns": ["x1", "x2", "cat"]},
    )
    # onehot of the categorical column inside the pipeline -> training succeeds.
    assert "train_accuracy" in meta.ml_metrics


def test_kmeans_clustering(ml_env):
    rng = np.random.RandomState(0)
    df = pd.DataFrame({
        "x": np.concatenate([rng.normal(0, 0.3, 50), rng.normal(5, 0.3, 50)]),
        "y": np.concatenate([rng.normal(0, 0.3, 50), rng.normal(5, 0.3, 50)]),
    })
    _, _, meta = _train(df, {"model_type": "kmeans", "seed": 0, "hyperparameters": {"n_clusters": 2}})
    assert meta.task_type == "clustering"
    assert meta.model_uri
    assert meta.ml_metrics["silhouette"] > 0.5


def test_reproducible_metrics_with_same_seed(ml_env):
    df = _classification_df()
    cfg = {"model_type": "random_forest_classifier", "target_column": "target", "seed": 42}
    _, _, m1 = _train(df, cfg)
    _, _, m2 = _train(df, cfg)
    assert m1.ml_metrics["train_accuracy"] == m2.ml_metrics["train_accuracy"]


# -- validation / guardrails ------------------------------------------------


def test_seed_required():
    with pytest.raises(ValueError, match="seed"):
        NODE.validate_config({"model_type": "ridge", "target_column": "y"})


def test_unknown_model_type_rejected():
    with pytest.raises(ValueError, match="Unknown model_type"):
        NODE.validate_config({"model_type": "deep_net", "target_column": "y", "seed": 1})


def test_target_in_features_is_leakage():
    with pytest.raises(ValueError, match="leakage"):
        NODE.validate_config({
            "model_type": "ridge", "target_column": "y", "seed": 1,
            "feature_columns": ["a", "y"],
        })


def test_supervised_requires_target():
    with pytest.raises(ValueError, match="target_column"):
        NODE.validate_config({"model_type": "ridge", "seed": 1})


def test_too_few_rows_rejected(ml_env):
    df = _classification_df(n=8)
    with pytest.raises(ValueError, match="at least"):
        _train(df, {"model_type": "logistic_regression", "target_column": "target", "seed": 1})


def test_cv_folds_exceeding_rows_rejected(ml_env):
    df = _classification_df(n=12)
    with pytest.raises(ValueError, match="CV"):
        _train(df, {"model_type": "logistic_regression", "target_column": "target",
                    "seed": 1, "cross_validate": True, "cv_folds": 20})


def test_model_size_limit_enforced(ml_env, monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_MAX_MODEL_SIZE_MB", "0")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="MB limit"):
        _train(_classification_df(),
               {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1})


def test_feature_column_limit_via_schema(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_MAX_FEATURE_COLUMNS", "2")
    get_settings.cache_clear()
    schema = MLSchema(columns=["a", "b", "c", "target"], row_count=100)
    with pytest.raises(ValueError, match="ML_MAX_FEATURE_COLUMNS"):
        NODE.validate_with_schema(
            {"model_type": "ridge", "target_column": "target", "seed": 1}, schema
        )
    get_settings.cache_clear()


def test_training_row_limit_via_schema(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_MAX_TRAINING_ROWS", "50")
    get_settings.cache_clear()
    schema = MLSchema(columns=["a", "target"], row_count=100)
    with pytest.raises(ValueError, match="ML_MAX_TRAINING_ROWS"):
        NODE.validate_with_schema(
            {"model_type": "ridge", "target_column": "target", "seed": 1}, schema
        )
    get_settings.cache_clear()


def test_missing_feature_column_rejected(ml_env):
    df = _classification_df()
    with pytest.raises(ValueError, match="not found"):
        _train(df, {"model_type": "ridge", "target_column": "target", "seed": 1,
                    "feature_columns": ["x1", "ghost"]})


# -- through the executor ----------------------------------------------------


def test_executor_runs_train_and_attaches_metadata(ml_env, tmp_path):
    csv = tmp_path / "in.csv"
    _classification_df().to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "tr", "type": "mlTrain", "data": {"config": {
                "model_type": "random_forest_classifier", "target_column": "target", "seed": 42}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "tr"},
            {"id": "e2", "source": "tr", "target": "o", "sourceHandle": "out"},
        ],
    }
    paths = {dataset_ref_key("ds1", None): csv}
    result = FlowExecutor().run_with_results(graph, paths, out_dir)
    assert result.error is None, result.error
    by_id = {r.node_id: r for r in result.node_results}
    assert by_id["tr"].task_type == "classification"
    assert by_id["tr"].model_uri
    assert "train_accuracy" in by_id["tr"].ml_metrics
    # the metadata round-trips through as_dict (what node_results_json stores).
    assert by_id["tr"].as_dict()["model_uri"] == by_id["tr"].model_uri
