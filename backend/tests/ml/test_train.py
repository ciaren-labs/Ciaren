"""mlTrain: training across tasks, MLflow logging, leakage detection, the
guardrail limits, and reproducibility. MLflow is pointed at a temp dir."""

import json

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.transformations.ml.base import MLSchema
from app.engine.transformations.ml.train import (
    TrainClassifierTransformation,
    TrainClusteringTransformation,
    TrainDimReductionTransformation,
    TrainForecasterTransformation,
    TrainRegressorTransformation,
)
from app.ml.models import get_model_spec

NODE = TrainClassifierTransformation()  # classifier-config method tests
REGRESSOR = TrainRegressorTransformation()

_NODE_BY_TASK = {
    "classification": TrainClassifierTransformation(),
    "regression": TrainRegressorTransformation(),
    "clustering": TrainClusteringTransformation(),
    "dimensionality_reduction": TrainDimReductionTransformation(),
    "timeseries": TrainForecasterTransformation(),
}


def node_for(config):
    """The task-scoped train node matching a config's model_type (classifier on
    an unknown type, so the 'unknown model_type' path still surfaces)."""
    try:
        task = get_model_spec(config.get("model_type", "")).task
    except Exception:
        return NODE
    return _NODE_BY_TASK.get(task, NODE)


@pytest.fixture
def ml_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CIAREN_MLFLOW_TRACKING_URI", str(tmp_path / "mlruns"))
    monkeypatch.setenv("CIAREN_ML_ARTIFACT_DIR", str(tmp_path / "artifacts"))
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
    out, meta = node_for(config).execute_with_metadata(engine, {"in": frame}, config)
    return engine, out, meta


# -- happy paths ------------------------------------------------------------


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_classification_trains_and_logs(ml_env, engine_name):
    engine, out, meta = _train(
        _classification_df(),
        {"model_type": "random_forest_classifier", "target_column": "target", "seed": 42},
        engine_name,
    )
    # mlTrain emits a single "model" output (the trained model reference).
    assert set(out) == {"model"}
    assert meta.task_type == "classification"
    # MLflow 3 returns a logged-model URI (models:/m-...); older returns runs:/...
    assert meta.model_uri and meta.model_uri.startswith(("models:/", "runs:/"))
    assert meta.mlflow_run_id
    assert "train_accuracy" in meta.ml_metrics
    # model reference frame carries the URI downstream.
    model_ref = engine.to_pandas(out["model"])
    assert model_ref.loc[0, "model_uri"] == meta.model_uri


def test_pinned_requirements_match_installed(ml_env):
    # Requirements are pinned to the actually-imported versions so MLflow's
    # load-time check (which reads the same metadata) never reports a spurious
    # mismatch. Core libs must always be present and exactly pinned.
    import importlib.metadata as md

    reqs = NODE._pinned_requirements({"model_type": "random_forest_classifier", "seed": 1})
    by_name = {r.split("==")[0]: r.split("==")[1] for r in reqs}
    for pkg in ("scikit-learn", "numpy", "pandas", "cloudpickle"):
        assert pkg in by_name
        assert by_name[pkg] == md.version(pkg)


def test_pinned_requirements_include_model_library(ml_env):
    reqs = NODE._pinned_requirements({"model_type": "xgboost_classifier", "seed": 1})
    assert any(r.startswith("xgboost==") for r in reqs)


def test_logged_model_has_signature(ml_env):
    # A signature is attached so the MLflow UI shows schema and load-time
    # validation works; it must not raise even for the happy path.
    _, _, meta = _train(
        _classification_df(),
        {"model_type": "logistic_regression", "target_column": "target", "seed": 7},
    )
    from app.ml.tracking import configure_mlflow

    mlflow = configure_mlflow()
    info = mlflow.models.get_model_info(meta.model_uri)
    assert info.signature is not None


def test_regression_trains(ml_env):
    _, _, meta = _train(
        _regression_df(),
        {"model_type": "linear_regression", "target_column": "target", "seed": 1},
    )
    assert meta.task_type == "regression"
    assert meta.ml_metrics["train_r2"] > 0.9  # strong linear signal


def test_model_reference_carries_estimator_config_for_downstream_cv(ml_env):
    engine, out, _ = _train(
        _classification_df(),
        {
            "model_type": "logistic_regression",
            "target_column": "target",
            "feature_columns": ["x1", "x2"],
            "hyperparameters": {"max_iter": 200},
            "preprocessing": {"numeric_columns": ["x1", "x2"], "numeric_strategy": "standard_scaler"},
            "seed": 3,
        },
    )
    model_ref = engine.to_pandas(out["model"]).iloc[0]
    model_config = json.loads(model_ref["model_config_json"])
    assert model_config["model_type"] == "logistic_regression"
    assert model_config["target_column"] == "target"
    assert model_config["feature_columns"] == ["x1", "x2"]
    assert model_config["hyperparameters"] == {"max_iter": 200}
    assert model_config["preprocessing"]["numeric_strategy"] == "standard_scaler"


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
        {
            "model_type": "logistic_regression",
            "target_column": "target",
            "seed": 5,
            "feature_columns": ["x1", "x2", "cat"],
        },
    )
    # onehot of the categorical column inside the pipeline -> training succeeds.
    assert "train_accuracy" in meta.ml_metrics


def test_kmeans_clustering(ml_env):
    rng = np.random.RandomState(0)
    df = pd.DataFrame(
        {
            "x": np.concatenate([rng.normal(0, 0.3, 50), rng.normal(5, 0.3, 50)]),
            "y": np.concatenate([rng.normal(0, 0.3, 50), rng.normal(5, 0.3, 50)]),
        }
    )
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
        REGRESSOR.validate_config(
            {
                "model_type": "ridge",
                "target_column": "y",
                "seed": 1,
                "feature_columns": ["a", "y"],
            }
        )


def test_supervised_requires_target():
    with pytest.raises(ValueError, match="target_column"):
        REGRESSOR.validate_config({"model_type": "ridge", "seed": 1})


def test_too_few_rows_rejected(ml_env):
    df = _classification_df(n=8)
    with pytest.raises(ValueError, match="at least"):
        _train(df, {"model_type": "logistic_regression", "target_column": "target", "seed": 1})


def test_model_size_limit_enforced(ml_env, monkeypatch):
    monkeypatch.setenv("CIAREN_ML_MAX_MODEL_SIZE_MB", "0")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="MB limit"):
        _train(_classification_df(), {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1})


def test_feature_column_limit_via_schema(monkeypatch):
    monkeypatch.setenv("CIAREN_ML_MAX_FEATURE_COLUMNS", "2")
    get_settings.cache_clear()
    schema = MLSchema(columns=["a", "b", "c", "target"], row_count=100)
    with pytest.raises(ValueError, match="ML_MAX_FEATURE_COLUMNS"):
        NODE.validate_with_schema({"model_type": "ridge", "target_column": "target", "seed": 1}, schema)
    get_settings.cache_clear()


def test_training_row_limit_via_schema(monkeypatch):
    monkeypatch.setenv("CIAREN_ML_MAX_TRAINING_ROWS", "50")
    get_settings.cache_clear()
    schema = MLSchema(columns=["a", "target"], row_count=100)
    with pytest.raises(ValueError, match="ML_MAX_TRAINING_ROWS"):
        NODE.validate_with_schema({"model_type": "ridge", "target_column": "target", "seed": 1}, schema)
    get_settings.cache_clear()


def test_missing_feature_column_rejected(ml_env):
    df = _classification_df()
    with pytest.raises(ValueError, match="not found"):
        _train(df, {"model_type": "ridge", "target_column": "target", "seed": 1, "feature_columns": ["x1", "ghost"]})


# -- MLflow persistence failure must not report a clean success (F1) ----------


def test_log_model_failure_fails_the_node(ml_env, monkeypatch):
    """If the model can't be persisted (the known long-Windows-path MLflow
    failure), the node must fail loudly — not report SUCCESS with a model_ref
    whose model_uri is None, which would silently break every downstream node
    (and a train-only flow would look like it saved a model when it saved
    nothing)."""
    pytest.importorskip("mlflow")
    import mlflow.sklearn

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated artifact write failure (path too long)")

    monkeypatch.setattr(mlflow.sklearn, "log_model", _boom)
    with pytest.raises(RuntimeError, match="could not be saved to MLflow"):
        _train(
            _classification_df(),
            {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
        )


def test_param_logging_failure_still_saves_model(ml_env, monkeypatch):
    """The *secondary* metadata writes (params/metrics/tags) must degrade-and-warn:
    a bad param value can't stop a usable model from being saved (the preserved
    genuine-degrade path, distinct from a log_model persistence failure)."""
    pytest.importorskip("mlflow")
    import mlflow

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated params logging failure")

    monkeypatch.setattr(mlflow, "log_params", _boom)
    _, _, meta = _train(
        _classification_df(),
        {"model_type": "logistic_regression", "target_column": "target", "seed": 1},
    )
    # Model was still persisted despite the params-logging hiccup.
    assert meta.model_uri and meta.model_uri.startswith(("models:/", "runs:/"))


# -- through the executor ----------------------------------------------------


def test_executor_runs_train_and_attaches_metadata(ml_env, tmp_path):
    csv = tmp_path / "in.csv"
    _classification_df().to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # mlTrain is a valid terminal (it persists the model to MLflow), so this is a
    # complete train-only flow — no file-output node needed.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "random_forest_classifier", "target_column": "target", "seed": 42}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "tr"},
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
