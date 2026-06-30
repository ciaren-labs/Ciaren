"""Aggressive edge cases for the ML "model" handle topology.

The model wire is a distinct, type-checked connection: mlTrain emits a single
``model`` output; mlPredict / featureImportance consume it on a ``model`` input;
a model may only connect to a model input (and a model input only accepts a
model). These tests bound that contract from every angle — the pure registry
helpers, graph validation (both miswirings, counts, ordering), the mlPredict
model resolver, and a full executor round-trip on the new topology.
"""

import numpy as np
import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import GraphValidationError, validate_graph
from app.engine.node_kinds import (
    MODEL_INPUT_HANDLES,
    MODEL_OUTPUT_HANDLES,
    edge_carries_model,
    is_model_input_handle,
    output_handles,
    primary_output_handle,
)
from app.engine.transformations.ml.predict import MLPredictTransformation
from tests.ml.conftest import classification_df

# -- registry helpers (pure, exhaustive) ------------------------------------


def test_output_handles_for_model_and_multi_and_plain_nodes():
    assert output_handles("mlTrainClassifier") == ("model",)
    assert output_handles("trainTestSplit") == ("train", "test")
    assert output_handles("dropNulls") == ("out",)
    assert output_handles("featureImportance") == ("out",)  # model is an INPUT here
    assert primary_output_handle("mlTrainClassifier") == "model"


@pytest.mark.parametrize(
    "source_type,source_handle,expected",
    [
        ("mlTrainClassifier", None, True),  # single-output: resolves to its sole model handle
        ("mlTrainClassifier", "model", True),  # explicit, redundant but valid
        ("mlTrainClassifier", "out", False),  # wrong handle name -> not a model edge
        ("mlTrainClassifier", "wat", False),
        ("trainTestSplit", "train", False),  # split outputs are frames
        ("trainTestSplit", None, False),
        ("dropNulls", None, False),
        ("featureImportance", None, False),  # emits a frame ("out")
        ("", None, False),
        ("notARealType", None, False),
    ],
)
def test_edge_carries_model_matrix(source_type, source_handle, expected):
    assert edge_carries_model(source_type, source_handle) is expected


@pytest.mark.parametrize(
    "node_type,handle,expected",
    [
        ("mlPredict", "model", True),
        ("mlPredict", "in", False),
        ("featureImportance", "model", True),
        ("featureImportance", "in", False),
        ("dropNulls", "in", False),
        ("mlTrainClassifier", "model", False),  # mlTrain's "model" is an OUTPUT, not an input
    ],
)
def test_is_model_input_handle_matrix(node_type, handle, expected):
    assert is_model_input_handle(node_type, handle) is expected


def test_model_handle_tables_are_disjoint_in_intent():
    # A node that consumes a model never also produces one (and vice versa) — the
    # two roles are distinct, which keeps edge_carries_model unambiguous.
    assert set(MODEL_OUTPUT_HANDLES).isdisjoint(MODEL_INPUT_HANDLES)


# -- graph validation: every model miswiring is rejected --------------------


def _input(node_id="in1", dataset_id="ds1"):
    return {"id": node_id, "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}}


def _n(node_id, node_type, config=None):
    return {"id": node_id, "type": node_type, "data": {"config": config or {}}}


def _e(eid, source, target, target_handle=None, source_handle=None):
    e = {"id": eid, "source": source, "target": target}
    if target_handle is not None:
        e["targetHandle"] = target_handle
    if source_handle is not None:
        e["sourceHandle"] = source_handle
    return e


_RIDGE = {"model_type": "ridge", "target_column": "y", "seed": 1}


def test_model_into_file_output_rejected():
    graph = {
        "nodes": [_input(), _n("tr", "mlTrainRegressor", _RIDGE), _n("out", "csvOutput")],
        "edges": [_e("e1", "in1", "tr"), _e("e2", "tr", "out")],
    }
    with pytest.raises(GraphValidationError, match="model can only connect to a model input"):
        validate_graph(graph)


def test_model_into_evaluate_data_input_rejected():
    graph = {
        "nodes": [
            _input(),
            _n("tr", "mlTrainRegressor", _RIDGE),
            _n("ev", "mlEvaluate", {"task_type": "regression", "target_column": "y", "prediction_column": "p"}),
            _n("out", "csvOutput"),
        ],
        "edges": [_e("e1", "in1", "tr"), _e("e2", "tr", "ev"), _e("e3", "ev", "out")],
    }
    with pytest.raises(GraphValidationError, match="model can only connect to a model input"):
        validate_graph(graph)


def test_model_into_another_trains_data_input_rejected():
    graph = {
        "nodes": [
            _input(),
            _n("tr1", "mlTrainRegressor", _RIDGE),
            _n("tr2", "mlTrainRegressor", _RIDGE),
        ],
        "edges": [_e("e1", "in1", "tr1"), _e("e2", "tr1", "tr2")],  # model -> mlTrain.in
    }
    with pytest.raises(GraphValidationError, match="model can only connect to a model input"):
        validate_graph(graph)


def test_data_into_model_input_rejected_predict():
    # "in" is satisfied by real data; the offending edge is data wired into the
    # "model" input, which must be rejected as "needs a model reference".
    graph = {
        "nodes": [_input(), _n("pr", "mlPredict"), _n("out", "csvOutput")],
        "edges": [
            _e("e1", "in1", "pr"),  # data into the "in" handle (required)
            _e("e2", "in1", "pr", target_handle="model"),  # data into "model" — wrong
            _e("e3", "pr", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="needs a model reference"):
        validate_graph(graph)


def test_model_wired_into_predict_data_input_rejected():
    # A model wired into the data "in" handle (its sole incoming edge) must be
    # rejected — the model belongs on the "model" handle.
    graph = {
        "nodes": [_input(), _n("tr", "mlTrainRegressor", _RIDGE), _n("pr", "mlPredict"), _n("out", "csvOutput")],
        "edges": [
            _e("e1", "in1", "tr"),
            _e("e2", "tr", "pr"),  # model into "in" (default handle) — wrong
            _e("e3", "pr", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="model can only connect to a model input"):
        validate_graph(graph)


def test_two_models_into_one_model_input_rejected():
    graph = {
        "nodes": [
            _input(),
            _n("tr1", "mlTrainRegressor", _RIDGE),
            _n("tr2", "mlTrainRegressor", _RIDGE),
            _n("fi", "featureImportance"),
            _n("out", "csvOutput"),
        ],
        "edges": [
            _e("e1", "in1", "tr1"),
            _e("e2", "in1", "tr2"),
            _e("e3", "tr1", "fi", target_handle="model"),
            _e("e4", "tr2", "fi", target_handle="model"),  # second model into one input
            _e("e5", "fi", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="only one connection"):
        validate_graph(graph)


def test_feature_importance_without_model_rejected():
    graph = {
        "nodes": [_input(), _n("fi", "featureImportance"), _n("out", "csvOutput")],
        "edges": [_e("e1", "fi", "out")],  # nothing feeds fi
    }
    with pytest.raises(GraphValidationError, match="not connected"):
        validate_graph(graph)


def test_full_model_topology_is_valid():
    # split.test -> predict.in, split.train -> train -> predict.model + fi.model.
    graph = {
        "nodes": [
            _input(),
            _n("sp", "trainTestSplit", {"seed": 1}),
            _n("tr", "mlTrainRegressor", _RIDGE),
            _n("pr", "mlPredict"),
            _n("fi", "featureImportance"),
            _n(
                "ev",
                "mlEvaluate",
                {"task_type": "regression", "target_column": "y", "prediction_column": "prediction"},
            ),
            _n("m", "csvOutput"),
            _n("f", "csvOutput"),
        ],
        "edges": [
            _e("e1", "in1", "sp"),
            _e("e2", "sp", "tr", target_handle="in", source_handle="train"),
            _e("e3", "sp", "pr", target_handle="in", source_handle="test"),
            _e("e4", "tr", "pr", target_handle="model"),
            _e("e5", "tr", "fi", target_handle="model"),
            _e("e6", "pr", "ev"),
            _e("e7", "ev", "m"),
            _e("e8", "fi", "f"),
        ],
    }
    validate_graph(graph)  # no raise


# -- mlPredict model resolver edge cases ------------------------------------

NODE = MLPredictTransformation()


def test_resolver_rejects_placeholder_model_uri_none():
    # A preview placeholder (model_uri=None) leaking into a real run must error,
    # not try to load None.
    engine = get_engine("pandas")
    frame = engine.from_pandas(pd.DataFrame([{"model_uri": None, "task_type": "classification"}]))
    with pytest.raises(ValueError, match="no model to load"):
        NODE._resolve_model(engine, {"in": frame, "model": frame}, {})


def test_resolver_rejects_nan_model_uri_cell():
    engine = get_engine("pandas")
    frame = engine.from_pandas(pd.DataFrame([{"model_uri": np.nan, "task_type": "regression"}]))
    with pytest.raises(ValueError, match="no model to load"):
        NODE._resolve_model(engine, {"model": frame}, {})


def test_resolver_rejects_empty_model_frame():
    engine = get_engine("pandas")
    frame = engine.from_pandas(pd.DataFrame({"model_uri": pd.Series([], dtype="object")}))
    with pytest.raises(ValueError, match="no model to load"):
        NODE._resolve_model(engine, {"model": frame}, {})


def test_resolver_config_uri_takes_precedence_over_wired_model():
    # When both a model wire and a model_uri are present, the explicit config URI
    # wins (an intentional override); task still comes from the wired reference.
    engine = get_engine("pandas")
    frame = engine.from_pandas(pd.DataFrame([{"model_uri": "runs:/wired", "task_type": "classification"}]))
    uri, task = NODE._resolve_model(engine, {"model": frame}, {"model_uri": "models:/override@prod"})
    assert uri == "models:/override@prod"
    assert task == "classification"


# -- executor round-trip on the new single-output topology ------------------


def test_executor_train_to_feature_importance_via_model_handle(ml_env, tmp_path):
    """mlTrain (single model output) -> featureImportance (model handle) -> output,
    end-to-end through the executor — bounds the new topology beyond codegen."""
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
                "data": {"config": {"model_type": "random_forest_classifier", "target_column": "target", "seed": 0}},
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
    paths = {dataset_ref_key("ds1", None): csv}
    result = FlowExecutor().run_with_results(graph, paths, out_dir)
    assert result.error is None, result.error
    by_id = {r.node_id: r for r in result.node_results}
    # mlTrain's sampled (primary) frame is the model reference, not training data.
    assert by_id["tr"].columns[:3] == ["mlflow_run_id", "model_uri", "task_type"]
    assert "model_config_json" in by_id["tr"].columns
    assert by_id["tr"].model_uri
    fi_csv = pd.read_csv(result.output_paths["out"])
    assert list(fi_csv.columns) == ["feature_name", "importance", "rank"]
    assert set(fi_csv["feature_name"]) == {"x1", "x2"}
