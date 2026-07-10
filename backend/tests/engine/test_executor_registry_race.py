"""In-flight runs must survive a concurrent plugin reload.

Enabling/disabling a plugin (or changing its grants) calls ``reload_plugins``,
which unregisters plugin nodes from the global engine registry and re-registers
them. The executor used to resolve each node's transformation lazily at
execution time, so a reload landing mid-run crashed the run with a KeyError.
It now snapshots every transformation up front and finishes on those references.

The race is simulated deterministically: a test transformation that, when
executed, unregisters a type a *downstream* node still needs — exactly what a
reload does under an in-flight run.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import GraphValidationError
from app.engine.registry import (
    get_transformation,
    register_transformations,
    unregister_transformations,
)
from app.engine.transformations.base import BaseTransformation
from app.engine.transformations.nulls import DropNullsTransformation


class _UnregisterDownstreamMidRun(BaseTransformation):
    """Passthrough that rips ``dropNulls`` out of the registry while executing,
    the way ``reload_plugins`` does to plugin nodes under an in-flight run."""

    type = "testRegistryRaceTrigger"

    def validate_config(self, config: dict[str, Any]) -> None:
        pass

    def execute(self, engine, inputs, config):
        unregister_transformations("dropNulls")
        return {"out": inputs["in"]}

    def to_python_code(self, *args, **kwargs):  # pragma: no cover - never emitted
        raise NotImplementedError

    def to_polars_code(self, *args, **kwargs):  # pragma: no cover - never emitted
        raise NotImplementedError


def _graph() -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "trigger", "type": "testRegistryRaceTrigger", "data": {"config": {}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "trigger"},
            {"id": "e2", "source": "trigger", "target": "drop"},
            {"id": "e3", "source": "drop", "target": "out1"},
        ],
    }


@pytest.fixture
def _race_registry():
    register_transformations(_UnregisterDownstreamMidRun())
    try:
        yield
    finally:
        unregister_transformations("testRegistryRaceTrigger")
        # Restore dropNulls if a test's mid-run unregistration was reached.
        try:
            get_transformation("dropNulls")
        except KeyError:
            register_transformations(DropNullsTransformation())


def _input_csv(tmp_path: Path) -> Path:
    path = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2, None], "b": [4, 5, 6]}).to_csv(path, index=False)
    return path


def test_run_survives_mid_run_unregistration(tmp_path: Path, _race_registry) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    paths = {dataset_ref_key("ds1", None): _input_csv(tmp_path)}

    result = FlowExecutor().run_with_results(_graph(), paths, out_dir, engine_name="pandas")

    assert result.error is None, result.error
    statuses = {r.node_id: r.status for r in result.node_results}
    assert statuses == {"in1": "success", "trigger": "success", "drop": "success", "out1": "success"}
    assert (out_dir / "out1.csv").exists()
    # The simulated reload really did remove the type mid-run.
    with pytest.raises(KeyError):
        get_transformation("dropNulls")


def test_preview_survives_mid_run_unregistration(tmp_path: Path, _race_registry) -> None:
    paths = {dataset_ref_key("ds1", None): _input_csv(tmp_path)}

    frames = FlowExecutor().compute_frames(_graph(), paths, get_engine("pandas"))

    assert len(frames["drop"]) == 2  # dropNulls executed despite the mid-run reload


def test_type_missing_at_start_fails_cleanly(tmp_path: Path, _race_registry) -> None:
    """A type already gone when the run starts is a clean validation error,
    not a mid-run crash."""
    graph = _graph()
    for node in graph["nodes"]:
        if node["type"] == "dropNulls":
            node["type"] = "definitelyNotRegistered"
    paths = {dataset_ref_key("ds1", None): _input_csv(tmp_path)}

    with pytest.raises(GraphValidationError, match="Unknown node type"):
        FlowExecutor().run_with_results(graph, paths, tmp_path / "out2", engine_name="pandas")
