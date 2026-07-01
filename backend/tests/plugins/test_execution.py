"""End-to-end: a plugin-contributed node runs in the engine and exports to code.

Loads the bundled example plugin from a directory, bridges it into the engine
registry, and exercises the full pipeline: registration, graph validation,
execution on both engines, and pandas + polars code export.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.engine.codegen import CodeGenerator
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import validate_graph
from app.engine.polars_codegen import PolarsCodeGenerator
from app.engine.registry import get_transformation, list_transformation_types
from app.plugins import get_registry, reset_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples" / "plugins"


@pytest.fixture(autouse=True)
def _load_example_plugin(monkeypatch):
    from app.plugins.state import PluginStateStore

    monkeypatch.setenv("CIAREN_PLUGINS_DIR", str(EXAMPLES_DIR))
    # Plugins now require explicit approval before their code is imported, even
    # with zero declared permissions. Pre-approve the example so it loads.
    state = PluginStateStore()
    state.set_approved("community.hello", True)
    state.save()
    reset_registry()
    get_registry()  # discovers + bridges the example plugin into the engine
    yield
    reset_registry()  # unregister the bridged node so other tests stay clean


def _graph():
    """csvInput -> hello.greeting -> csvOutput."""
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "greet",
                "type": "hello.greeting",
                "data": {"config": {"column": "msg", "name": "Ciaren"}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "greet"},
            {"id": "e2", "source": "greet", "target": "out1"},
        ],
    }


def test_plugin_node_registered_in_engine():
    assert "hello.greeting" in list_transformation_types()
    tf = get_transformation("hello.greeting")
    assert tf.type == "hello.greeting"
    assert tf.input_handles == ("in",)


def test_graph_validation_accepts_plugin_node():
    validate_graph(_graph())  # should not raise


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_run_pipeline_with_plugin_node(tmp_path, engine_name):
    in_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2, 3]}).to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    outputs = FlowExecutor().execute(
        _graph(),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name=engine_name,
    )
    result = pd.read_csv(outputs["out1"])
    assert list(result["msg"]) == ["Hello, Ciaren!"] * 3
    assert list(result["a"]) == [1, 2, 3]


def test_export_python_with_plugin_node():
    code = CodeGenerator().generate(_graph(), {"ds1": "in.csv"})
    assert ".assign(" in code
    assert "'msg': 'Hello, Ciaren!'" in code


def test_export_polars_with_plugin_node():
    code = PolarsCodeGenerator().generate(_graph(), {"ds1": "in.csv"})
    # The pandas-emitting plugin node is bridged in the polars script.
    assert "to_pandas()" in code
    assert "from_pandas(" in code
    assert "'msg': 'Hello, Ciaren!'" in code


def test_reset_unregisters_plugin_node():
    assert "hello.greeting" in list_transformation_types()
    reset_registry()
    assert "hello.greeting" not in list_transformation_types()
