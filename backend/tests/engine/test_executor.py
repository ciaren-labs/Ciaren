import pandas as pd
import pytest

from app.engine.codegen import CodeGenerator
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.graph import GraphValidationError


def _paths(**by_id):
    """Key dataset paths the way the engine resolves them (id -> 'id:latest')."""
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


def _pipeline_graph():
    """csvInput -> dropNulls -> renameColumns -> csvOutput."""
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {
                "id": "ren",
                "type": "renameColumns",
                "data": {"config": {"mapping": {"a": "alpha"}}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "ren"},
            {"id": "e3", "source": "ren", "target": "out1"},
        ],
    }


@pytest.fixture
def input_csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2, None], "b": [4, 5, 6]}).to_csv(path, index=False)
    return path


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_full_pipeline(tmp_path, input_csv, engine_name):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outputs = FlowExecutor().execute(
        _pipeline_graph(),
        dataset_paths=_paths(ds1=input_csv),
        output_dir=out_dir,
        engine_name=engine_name,
    )
    assert "out1" in outputs
    result = pd.read_csv(outputs["out1"])
    assert "alpha" in result.columns
    assert len(result) == 2  # one null row dropped


def test_join_pipeline(tmp_path):
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    pd.DataFrame({"id": [1, 2], "x": ["a", "b"]}).to_csv(left, index=False)
    pd.DataFrame({"id": [1, 2], "y": ["c", "d"]}).to_csv(right, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    graph = {
        "nodes": [
            {"id": "l", "type": "csvInput", "data": {"config": {"dataset_id": "L"}}},
            {"id": "r", "type": "csvInput", "data": {"config": {"dataset_id": "R"}}},
            {"id": "j", "type": "join", "data": {"config": {"on": "id", "how": "inner"}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "l", "target": "j", "targetHandle": "left"},
            {"id": "e2", "source": "r", "target": "j", "targetHandle": "right"},
            {"id": "e3", "source": "j", "target": "o"},
        ],
    }
    outputs = FlowExecutor().execute(graph, _paths(L=left, R=right), out_dir)
    result = pd.read_csv(outputs["o"])
    assert set(result.columns) == {"id", "x", "y"}


def test_concat_pipeline(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    pd.DataFrame({"v": [1, 2]}).to_csv(a, index=False)
    pd.DataFrame({"v": [3, 4]}).to_csv(b, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    graph = {
        "nodes": [
            {"id": "a", "type": "csvInput", "data": {"config": {"dataset_id": "A"}}},
            {"id": "b", "type": "csvInput", "data": {"config": {"dataset_id": "B"}}},
            {"id": "c", "type": "concatRows", "data": {"config": {}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "a", "target": "c"},
            {"id": "e2", "source": "b", "target": "c"},
            {"id": "e3", "source": "c", "target": "o"},
        ],
    }
    outputs = FlowExecutor().execute(graph, _paths(A=a, B=b), out_dir)
    result = pd.read_csv(outputs["o"])
    assert len(result) == 4


def test_unknown_engine_raises(tmp_path, input_csv):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with pytest.raises(ValueError, match="Unknown engine"):
        FlowExecutor().execute(_pipeline_graph(), _paths(ds1=input_csv), out_dir, "spark")


def test_graph_without_input_rejected(tmp_path):
    graph = {
        "nodes": [{"id": "o", "type": "csvOutput", "data": {"config": {}}}],
        "edges": [],
    }
    with pytest.raises(GraphValidationError):
        FlowExecutor().execute(graph, {}, tmp_path)


def test_codegen_produces_runnable_script():
    code = CodeGenerator().generate(_pipeline_graph(), {"ds1": "/data/in.csv"})
    assert "import pandas as pd" in code
    assert "pd.read_csv" in code
    assert ".dropna()" in code
    assert ".rename(columns={'a': 'alpha'})" in code
    assert ".to_csv(" in code
    # The generated script must at least compile.
    compile(code, "<generated>", "exec")
