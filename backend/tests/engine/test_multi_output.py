"""Executor support for multi-output nodes, sourceHandle routing, the
EmitsNodeMetadata side-channel, and engine.from_pandas — the foundation the ML
nodes build on. Uses lightweight stub transformations so it has no ML deps.
"""

from typing import Any

import pandas as pd
import pytest

from app.engine import node_kinds, registry
from app.engine.backends import get_engine
from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import GraphValidationError, validate_graph
from app.engine.transformations.base import (
    BaseTransformation,
    EmitsNodeMetadata,
    NodeMetadata,
)

# -- Stub nodes (registered for the duration of the test session) -----------


class _SplitStub(BaseTransformation):
    """Splits incoming rows into two outputs by row parity: 'even' and 'odd'."""

    type = "splitStub"
    input_handles = ("in",)

    def validate_config(self, config: dict[str, Any]) -> None:  # pragma: no cover - trivial
        pass

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        pdf = engine.to_pandas(inputs["in"]).reset_index(drop=True)
        even = pdf.iloc[::2].reset_index(drop=True)
        odd = pdf.iloc[1::2].reset_index(drop=True)
        return {"even": engine.from_pandas(even), "odd": engine.from_pandas(odd)}

    def to_python_code(self, input_vars, output_vars, config):  # pragma: no cover
        return ""

    def to_polars_code(self, input_vars, output_vars, config):  # pragma: no cover
        return ""


class _MetaStub(BaseTransformation, EmitsNodeMetadata):
    """Passes data through unchanged but emits ML-style metadata."""

    type = "metaStub"

    def validate_config(self, config: dict[str, Any]) -> None:  # pragma: no cover - trivial
        pass

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frames, _meta = self.execute_with_metadata(engine, inputs, config)
        return frames

    def execute_with_metadata(self, engine, inputs, config):
        meta = NodeMetadata(
            ml_metrics={"score": 0.5},
            model_uri="runs:/abc/model",
            task_type="classification",
            cv_scores=[0.4, 0.6],
        )
        return {"out": inputs["in"]}, meta

    def to_python_code(self, input_vars, output_vars, config):  # pragma: no cover
        return ""

    def to_polars_code(self, input_vars, output_vars, config):  # pragma: no cover
        return ""


@pytest.fixture(autouse=True)
def _register_stubs():
    registry._register(_SplitStub(), _MetaStub())
    node_kinds.MULTI_OUTPUT_NODES["splitStub"] = ("even", "odd")
    try:
        yield
    finally:
        registry._REGISTRY.pop("splitStub", None)
        registry._REGISTRY.pop("metaStub", None)
        node_kinds.MULTI_OUTPUT_NODES.pop("splitStub", None)


def _paths(**by_id):
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


@pytest.fixture
def input_csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame({"v": [0, 1, 2, 3, 4, 5]}).to_csv(path, index=False)
    return path


# -- from_pandas round trips on both engines --------------------------------


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_from_pandas_round_trip(engine_name):
    engine = get_engine(engine_name)
    pdf = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    frame = engine.from_pandas(pdf)
    back = engine.to_pandas(frame)
    pd.testing.assert_frame_equal(back.reset_index(drop=True), pdf)


# -- Multi-output routing ---------------------------------------------------


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_multi_output_routes_by_source_handle(tmp_path, input_csv, engine_name):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "splitStub", "data": {"config": {}}},
            {"id": "out_even", "type": "csvOutput", "data": {"config": {}}},
            {"id": "out_odd", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "out_even", "sourceHandle": "even"},
            {"id": "e3", "source": "sp", "target": "out_odd", "sourceHandle": "odd"},
        ],
    }
    outputs = FlowExecutor().execute(graph, _paths(ds1=input_csv), out_dir, engine_name)
    even = pd.read_csv(outputs["out_even"])
    odd = pd.read_csv(outputs["out_odd"])
    assert even["v"].tolist() == [0, 2, 4]
    assert odd["v"].tolist() == [1, 3, 5]


def test_multi_output_primary_handle_sampled_in_run_dag(tmp_path, input_csv):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "splitStub", "data": {"config": {}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "o", "sourceHandle": "even"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=input_csv), out_dir)
    assert result.error is None
    by_id = {r.node_id: r for r in result.node_results}
    # "even" is the declared primary handle -> 3 rows sampled for the run DAG.
    assert by_id["sp"].rows == 3


# -- sourceHandle validation ------------------------------------------------


def test_unknown_source_handle_rejected():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "splitStub", "data": {"config": {}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "o", "sourceHandle": "nope"},
        ],
    }
    with pytest.raises(GraphValidationError, match="unknown output"):
        validate_graph(graph)


def test_missing_source_handle_on_multi_output_rejected():
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "sp", "type": "splitStub", "data": {"config": {}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sp"},
            {"id": "e2", "source": "sp", "target": "o"},  # no sourceHandle
        ],
    }
    with pytest.raises(GraphValidationError, match="multiple outputs"):
        validate_graph(graph)


# -- Metadata side-channel --------------------------------------------------


def test_metadata_attached_to_node_result(tmp_path, input_csv):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "m", "type": "metaStub", "data": {"config": {}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "m"},
            {"id": "e2", "source": "m", "target": "o"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=input_csv), out_dir)
    assert result.error is None
    by_id = {r.node_id: r for r in result.node_results}
    meta_node = by_id["m"]
    assert meta_node.ml_metrics == {"score": 0.5}
    assert meta_node.model_uri == "runs:/abc/model"
    assert meta_node.task_type == "classification"
    assert meta_node.cv_scores == [0.4, 0.6]
    # round-trips through as_dict (what lands in node_results_json)
    assert meta_node.as_dict()["ml_metrics"] == {"score": 0.5}
    # ETL nodes carry None for every ML field.
    assert by_id["in1"].ml_metrics is None
    assert by_id["in1"].as_dict()["model_uri"] is None
