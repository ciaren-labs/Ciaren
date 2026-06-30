"""mlCrossValidate: CV strategies, scoring, validation guardrails, codegen,
and executor integration. The node consumes a model reference from a Train node."""

import json

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.transformations.ml.base import MLSchema
from app.engine.transformations.ml.cross_validation import CrossValidateTransformation
from app.ml.models import get_model_spec

NODE = CrossValidateTransformation()


def _classification_df(n=120):
    rng = np.random.RandomState(0)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = (x1 + x2 > 0).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "grp": np.arange(n) % 6, "target": y})


def _regression_df(n=60):
    rng = np.random.RandomState(1)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 3 * x1 - 2 * x2 + rng.normal(scale=0.1, size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": y})


def _run(df, config, engine_name="pandas"):
    engine = get_engine(engine_name)
    model_config = _model_config(config)
    cv_config = _cv_config(config)
    model_ref = _model_ref(engine, model_config)
    out, meta = NODE.execute_with_metadata(engine, {"in": engine.from_pandas(df), "model": model_ref}, cv_config)
    return engine.to_pandas(out["out"]), meta


def _base(**over):
    cfg = {"model_type": "logistic_regression", "target_column": "target", "feature_columns": ["x1", "x2"], "seed": 42}
    cfg.update(over)
    return cfg


def _model_config(config):
    return {
        "model_type": config["model_type"],
        "target_column": config.get("target_column"),
        "feature_columns": config.get("feature_columns") or [],
        "hyperparameters": config.get("hyperparameters") or {},
        "preprocessing": config.get("preprocessing") or {},
        "seed": config.get("seed", 42),
    }


def _cv_config(config):
    model_keys = {"model_type", "target_column", "feature_columns", "hyperparameters", "preprocessing"}
    return {k: v for k, v in config.items() if k not in model_keys}


def _model_ref(engine, model_config):
    spec = get_model_spec(model_config["model_type"])
    return engine.from_pandas(
        pd.DataFrame(
            [
                {
                    "mlflow_run_id": None,
                    "model_uri": None,
                    "task_type": spec.task,
                    "model_type": model_config["model_type"],
                    "target_column": model_config.get("target_column"),
                    "feature_columns_json": json.dumps(model_config.get("feature_columns") or []),
                    "model_config_json": json.dumps(model_config),
                }
            ]
        )
    )


# -- happy paths: every strategy --------------------------------------------


@pytest.mark.parametrize(
    "strategy,extra,expected_folds",
    [
        ("kfold", {}, 5),
        ("stratified_kfold", {}, 5),
        ("shuffle_split", {"test_size": 0.25}, 5),
        ("stratified_shuffle_split", {"test_size": 0.25}, 5),
        ("group_kfold", {"group_column": "grp", "n_splits": 3}, 3),
        ("time_series_split", {"n_splits": 4}, 4),
        ("repeated_kfold", {"n_repeats": 2}, 10),
    ],
)
def test_each_strategy_runs(strategy, extra, expected_folds):
    frame, meta = _run(_classification_df(), _base(cv_strategy=strategy, **extra))
    assert len(frame) == expected_folds
    assert list(frame.columns) == ["fold", "accuracy", "f1_weighted", "fit_time_s"]
    assert meta.cv_scores is not None and len(meta.cv_scores) == expected_folds
    assert "cv_mean" in meta.ml_metrics and "cv_std" in meta.ml_metrics
    assert meta.ml_metrics["cv_accuracy_mean"] > 0.8  # strong signal
    assert meta.task_type == "classification"


def test_leave_one_out_regression():
    frame, meta = _run(
        _regression_df(),
        _base(model_type="linear_regression", cv_strategy="leave_one_out", scoring=["neg_mean_absolute_error"]),
    )
    # one fold per row
    assert len(frame) == len(_regression_df())
    # neg_ scores are negated + renamed so the report reads positive.
    assert "mean_absolute_error" in frame.columns
    assert meta.ml_metrics["cv_mean"] >= 0


def test_default_scoring_by_task():
    _, cls = _run(_classification_df(), _base(cv_strategy="kfold"))
    assert "cv_accuracy_mean" in cls.ml_metrics
    _, reg = _run(_regression_df(), _base(model_type="ridge", cv_strategy="kfold"))
    # default regression scoring: r2 + rmse (neg_ renamed)
    assert "cv_r2_mean" in reg.ml_metrics
    assert "cv_root_mean_squared_error_mean" in reg.ml_metrics


def test_reproducible_with_same_seed():
    a, _ = _run(_classification_df(), _base(cv_strategy="kfold"))
    b, _ = _run(_classification_df(), _base(cv_strategy="kfold"))
    assert a["accuracy"].tolist() == b["accuracy"].tolist()


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_runs_on_both_engines(engine_name):
    frame, meta = _run(_classification_df(), _base(cv_strategy="stratified_kfold"), engine_name)
    assert len(frame) == 5
    assert meta.cv_scores is not None


# -- validation guardrails ---------------------------------------------------


def test_seed_required():
    with pytest.raises(ValueError, match="seed"):
        NODE.validate_config({"model_type": "logistic_regression", "target_column": "target", "cv_strategy": "kfold"})


def test_target_required():
    with pytest.raises(ValueError, match="target_column"):
        _run(_classification_df(), _base(target_column=None, cv_strategy="kfold"))


def test_unsupervised_model_rejected():
    with pytest.raises(ValueError, match="classification and regression"):
        _run(_classification_df(), _base(model_type="kmeans", target_column=None))


def test_unknown_strategy_rejected():
    with pytest.raises(ValueError, match="cv_strategy"):
        NODE.validate_config(_base(cv_strategy="bogus"))


def test_stratified_requires_classification():
    with pytest.raises(ValueError, match="classification"):
        _run(_regression_df(), _base(model_type="ridge", cv_strategy="stratified_kfold"))


def test_group_strategy_requires_group_column():
    with pytest.raises(ValueError, match="group_column"):
        NODE.validate_config(_base(cv_strategy="group_kfold"))


def test_bad_n_splits_rejected():
    with pytest.raises(ValueError, match="n_splits"):
        NODE.validate_config(_base(cv_strategy="kfold", n_splits=1))


def test_bad_test_size_rejected():
    with pytest.raises(ValueError, match="test_size"):
        NODE.validate_config(_base(cv_strategy="shuffle_split", test_size=1.5))


def test_unsupported_scoring_rejected():
    with pytest.raises(ValueError, match="scoring"):
        NODE.validate_config(_base(cv_strategy="kfold", scoring=["silhouette"]))


def test_target_in_features_is_leakage():
    with pytest.raises(ValueError, match="leakage"):
        _run(_classification_df(), _base(feature_columns=["x1", "target"]))


def test_schema_rejects_too_many_folds():
    schema = MLSchema(columns=["x1", "x2", "target"], row_count=4)
    with pytest.raises(ValueError, match="rows"):
        NODE.validate_with_schema(_base(cv_strategy="kfold", n_splits=5), schema)


def test_schema_rejects_missing_target():
    with pytest.raises(ValueError, match="target_column"):
        _run(_classification_df(), _base(target_column="missing", cv_strategy="kfold"))


def test_feature_limit_via_schema(monkeypatch):
    monkeypatch.setenv("FLOWFRAME_ML_MAX_FEATURE_COLUMNS", "1")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="ML_MAX_FEATURE_COLUMNS"):
        _run(_classification_df(), _base(cv_strategy="kfold"))
    get_settings.cache_clear()


# -- codegen -----------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy,extra",
    [
        ("kfold", {}),
        ("stratified_kfold", {}),
        ("shuffle_split", {"test_size": 0.2}),
        ("group_kfold", {"group_column": "grp"}),
        ("time_series_split", {}),
        ("repeated_kfold", {"n_repeats": 2}),
        ("leave_one_out", {}),
    ],
)
def test_codegen_compiles(strategy, extra):
    cfg = _base(model_type="random_forest_classifier", cv_strategy=strategy, **extra)
    code = NODE.to_python_code({"in": "df", "model": "model_ref"}, {"out": "result"}, _cv_config(cfg))
    full = "import pandas as pd\n" + "\n".join(NODE.imports(cfg)) + "\n" + code
    compile(full, "<gen>", "exec")


def test_codegen_group_uses_input_var():
    cfg = _base(cv_strategy="group_kfold", group_column="grp")
    code = NODE.to_python_code({"in": "df", "model": "model_ref"}, {"out": "result"}, _cv_config(cfg))
    assert "groups=df['grp']" in code


# -- executor integration ----------------------------------------------------


def test_executor_runs_cv_as_terminal(tmp_path):
    csv = tmp_path / "in.csv"
    _classification_df().to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # No output node: a cross-validation node is a valid flow terminal.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "model",
                "type": "mlClassifierModel",
                "data": {
                    "config": {
                        "model_type": "logistic_regression",
                        "target_column": "target",
                        "feature_columns": ["x1", "x2"],
                        "hyperparameters": {},
                        "seed": 42,
                    }
                },
            },
            {
                "id": "cv",
                "type": "mlCrossValidate",
                "data": {
                    "config": {
                        "cv_strategy": "stratified_kfold",
                        "n_splits": 4,
                        "seed": 42,
                    }
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "model"},
            {"id": "e2", "source": "in1", "target": "cv"},
            {"id": "e3", "source": "model", "target": "cv", "sourceHandle": "model", "targetHandle": "model"},
        ],
    }
    paths = {dataset_ref_key("ds1", None): csv}
    result = FlowExecutor().run_with_results(graph, paths, out_dir)
    assert result.error is None, result.error
    cv = {r.node_id: r for r in result.node_results}["cv"]
    assert cv.task_type == "classification"
    assert cv.cv_scores and len(cv.cv_scores) == 4
    assert "cv_mean" in cv.ml_metrics
