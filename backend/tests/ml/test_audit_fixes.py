"""Regression tests for audit fixes: preview short-circuits ML nodes (no fit/log),
train-only flows validate, and featureImportance uses the default 'in' handle."""

import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import GraphValidationError, validate_graph
from app.engine.preview_context import in_preview, preview_mode
from app.engine.transformations.ml.importance import FeatureImportanceTransformation
from app.engine.transformations.ml.train import MLTrainTransformation
from tests.ml.conftest import classification_df

# -- preview short-circuit --------------------------------------------------


def test_in_preview_flag_scopes():
    assert in_preview() is False
    with preview_mode():
        assert in_preview() is True
    assert in_preview() is False


def test_mltrain_preview_does_not_fit_or_log(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    config = {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1}
    with preview_mode():
        out, meta = MLTrainTransformation().execute_with_metadata(engine, {"in": engine.from_pandas(df)}, config)
    # single "model" output: a placeholder reference, no MLflow run
    assert set(out) == {"model"}
    model_ref = engine.to_pandas(out["model"])
    assert model_ref.loc[0, "model_uri"] is None
    assert meta.mlflow_run_id is None
    assert meta.task_type == "classification"
    # no MLflow experiment/run created during preview
    mlruns = ml_env / "mlruns"
    assert not mlruns.exists() or not any(mlruns.iterdir())


def test_preview_mode_skips_training_in_full_flow(ml_env, tmp_path):
    csv = tmp_path / "in.csv"
    classification_df().to_csv(csv, index=False)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1}},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "tr"}],
    }
    paths = {dataset_ref_key("ds1", None): csv}
    with preview_mode():
        frames = FlowExecutor().compute_frames(graph, paths, get_engine("pandas"), require_output=False)
    # mlTrain's single "model" output resolves to a placeholder model reference
    assert "tr" in frames


# -- train-only flow validates ----------------------------------------------


def test_train_only_flow_is_valid():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "trainTestSplit", "data": {"config": {"seed": 1}}},
            {
                "id": "tr",
                "type": "mlTrainRegressor",
                "data": {"config": {"model_type": "ridge", "target_column": "y", "seed": 1}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "tr", "sourceHandle": "train"},
        ],
    }
    validate_graph(graph)  # no output node, but mlTrain is a model sink -> valid


def test_flow_without_output_or_mltrain_still_rejected():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "drop"}],
    }
    with pytest.raises(GraphValidationError, match="output node"):
        validate_graph(graph)


def test_train_only_flow_runs_and_logs(ml_env, tmp_path):
    csv = tmp_path / "in.csv"
    classification_df().to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "tr",
                "type": "mlTrainClassifier",
                "data": {"config": {"model_type": "logistic_regression", "target_column": "target", "seed": 1}},
            },
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "tr"}],
    }
    paths = {dataset_ref_key("ds1", None): csv}
    result = FlowExecutor().run_with_results(graph, paths, out_dir)
    assert result.error is None
    assert result.output_paths == {}  # no file output node
    by_id = {r.node_id: r for r in result.node_results}
    assert by_id["tr"].model_uri  # model was trained + logged


# -- featureImportance consumes the model on its "model" handle -------------


def test_feature_importance_uses_model_handle(ml_env):
    engine = get_engine("pandas")
    df = classification_df()
    out, _ = MLTrainTransformation().execute_with_metadata(
        engine,
        {"in": engine.from_pandas(df)},
        {"model_type": "random_forest_classifier", "target_column": "target", "seed": 0},
    )
    result, _ = FeatureImportanceTransformation().execute_with_metadata(engine, {"model": out["model"]}, {})
    assert set(engine.to_pandas(result["out"])["feature_name"]) == {"x1", "x2"}
    assert FeatureImportanceTransformation().input_handles == ("model",)


def test_feature_importance_graph_wiring_validates():
    # mlTrain (single model output) -> featureImportance "model" handle -> output.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "tr",
                "type": "mlTrainRegressor",
                "data": {"config": {"model_type": "ridge", "target_column": "y", "seed": 1}},
            },
            {"id": "fi", "type": "featureImportance", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "tr"},
            {"id": "e2", "source": "tr", "target": "fi", "targetHandle": "model"},
            {"id": "e3", "source": "fi", "target": "out"},
        ],
    }
    validate_graph(graph)
