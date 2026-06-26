"""Tests for the pythonTransform node.

Covers: valid scripts, syntax errors, wrong return type, engine-matrix
(pd / pl namespace available), codegen smoke tests, and executor integration.
"""

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.executor import FlowExecutor, dataset_ref_key
from app.engine.registry import get_transformation


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def run_script(engine, script: str, pdf: pd.DataFrame, **extra_config):
    t = get_transformation("pythonTransform")
    config = {"script": script, **extra_config}
    t.validate_config(config)
    ins = {"in": _native(engine, pdf)}
    frames = t.execute(engine, ins, config)
    return engine.to_pandas(frames["out"])


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


def test_validate_rejects_empty_script():
    t = get_transformation("pythonTransform")
    with pytest.raises(ValueError, match="non-empty"):
        t.validate_config({"script": "  "})


def test_validate_rejects_missing_script():
    t = get_transformation("pythonTransform")
    with pytest.raises(ValueError, match="non-empty"):
        t.validate_config({})


def test_validate_catches_syntax_error():
    t = get_transformation("pythonTransform")
    with pytest.raises(ValueError, match="syntax error"):
        t.validate_config({"script": "return df[["})


def test_validate_accepts_valid_script():
    t = get_transformation("pythonTransform")
    t.validate_config({"script": "return df"})


def test_validate_accepts_multiline_script():
    t = get_transformation("pythonTransform")
    t.validate_config({"script": "mask = df['x'] > 0\nreturn df[mask]"})


# ---------------------------------------------------------------------------
# execute — basic behaviour
# ---------------------------------------------------------------------------


def test_passthrough(engine):
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    out = run_script(engine, "return df", pdf)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), pdf)


def test_filter_rows(engine):
    pdf = pd.DataFrame({"x": [1, 2, 3, 4]})
    if engine.name == "polars":
        script = "import polars as pl; return df.filter(pl.col('x') > 2)"
    else:
        script = "return df[df['x'] > 2]"
    out = run_script(engine, script, pdf)
    assert len(out) == 2
    assert list(out["x"]) == [3, 4]


def test_add_column_pandas_engine():
    engine = get_engine("pandas")
    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = run_script(engine, "df['c'] = df['a'] + df['b']\nreturn df", pdf)
    assert list(out["c"]) == [4, 6]


def test_add_column_polars_engine():
    engine = get_engine("polars")
    pdf = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = run_script(
        engine,
        "import polars as pl\nreturn df.with_columns((pl.col('a') + pl.col('b')).alias('c'))",
        pdf,
    )
    assert list(out["c"]) == [4, 6]


def test_script_can_use_pd_namespace():
    """The pandas namespace injects 'pd' so scripts don't need to import it."""
    engine = get_engine("pandas")
    pdf = pd.DataFrame({"a": [1, None, 3]})
    out = run_script(engine, "return pd.DataFrame({'a': df['a'].fillna(0)})", pdf)
    assert list(out["a"]) == [1.0, 0.0, 3.0]


def test_script_can_use_pl_namespace():
    """The polars namespace injects 'pl' so scripts don't need to import it."""
    engine = get_engine("polars")
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    out = run_script(engine, "return df.filter(pl.col('a') >= 2)", pdf)
    assert list(out["a"]) == [2, 3]


def test_none_return_raises():
    engine = get_engine("pandas")
    pdf = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="returned None"):
        run_script(engine, "result = df  # forgot return", pdf)


def test_empty_dataframe(engine):
    pdf = pd.DataFrame({"a": pd.Series([], dtype=int)})
    out = run_script(engine, "return df", pdf)
    assert len(out) == 0
    assert "a" in out.columns


def test_script_drops_all_rows(engine):
    pdf = pd.DataFrame({"x": [1, 2, 3]})
    if engine.name == "polars":
        script = "import polars as pl; return df.filter(pl.col('x') > 100)"
    else:
        script = "return df[df['x'] > 100]"
    out = run_script(engine, script, pdf)
    assert len(out) == 0


def test_multiline_script(engine):
    pdf = pd.DataFrame({"a": [1, 2, 3, 4, 5]})
    if engine.name == "polars":
        script = "import polars as pl\nfiltered = df.filter(pl.col('a') > 2)\nreturn filtered"
    else:
        script = "mask = df['a'] > 2\nfiltered = df[mask]\nreturn filtered"
    out = run_script(engine, script, pdf)
    assert len(out) == 3


def test_script_can_import_stdlib(engine):
    """Scripts can import stdlib modules without restriction."""
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    out = run_script(engine, "import math\nreturn df", pdf)
    assert len(out) == 3


# ---------------------------------------------------------------------------
# Codegen smoke tests
# ---------------------------------------------------------------------------


def _exec_pandas_codegen(code: str, df_in: pd.DataFrame) -> pd.DataFrame:
    ns: dict = {"df_1": df_in, "pd": pd}
    exec(code, ns)  # noqa: S102
    return ns["df_2"]


def _exec_polars_codegen(code: str, df_in: pl.DataFrame) -> pl.DataFrame:
    ns: dict = {"df_1": df_in, "pl": pl}
    exec(code, ns)  # noqa: S102
    return ns["df_2"]


def test_pandas_codegen_passthrough():
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, {"script": "return df"})
    out = _exec_pandas_codegen(code, pdf)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), pdf)


def test_pandas_codegen_filter():
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"x": [1, 2, 3, 4]})
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, {"script": "return df[df['x'] > 2]"})
    out = _exec_pandas_codegen(code, pdf)
    assert len(out) == 2


def test_polars_codegen_passthrough():
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"script": "return df"})
    df_in = pl.from_pandas(pdf)
    out = _exec_polars_codegen(code, df_in)
    assert out.shape == df_in.shape


def test_polars_codegen_filter():
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"x": [1, 2, 3, 4]})
    script = "import polars as pl\nreturn df.filter(pl.col('x') > 2)"
    code = t.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"script": script})
    df_in = pl.from_pandas(pdf)
    out = _exec_polars_codegen(code, df_in)
    assert out.height == 2


def test_codegen_multiline_script():
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"a": [1, 2, 3]})
    script = "filtered = df[df['a'] > 1]\nreturn filtered"
    code = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, {"script": script})
    out = _exec_pandas_codegen(code, pdf)
    assert len(out) == 2


def test_multiple_codegen_blocks_independent():
    """Two pythonTransform nodes in one script don't conflict."""
    t = get_transformation("pythonTransform")
    pdf = pd.DataFrame({"x": [1, 2, 3, 4, 5]})

    code1 = t.to_python_code({"in": "df_1"}, {"out": "df_2"}, {"script": "return df[df['x'] > 2]"})
    code2 = t.to_python_code({"in": "df_2"}, {"out": "df_3"}, {"script": "return df[df['x'] < 5]"})

    ns: dict = {"df_1": pdf, "pd": pd}
    exec(code1, ns)  # noqa: S102
    exec(code2, ns)  # noqa: S102
    out = ns["df_3"]
    assert list(out["x"]) == [3, 4]


# ---------------------------------------------------------------------------
# Executor integration
# ---------------------------------------------------------------------------


def _paths(**by_id: Path):
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "data.csv"
    pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}).to_csv(path, index=False)
    return path


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_executor_python_transform(tmp_path: Path, sample_csv: Path, engine_name: str):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "py1",
                "type": "pythonTransform",
                # .head(2) works on both pandas and polars DataFrames.
                "data": {"config": {"script": "return df.head(2)"}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "py1"},
            {"id": "e2", "source": "py1", "target": "out1"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir, engine_name=engine_name)
    assert result.error is None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["py1"].status == "success"
    assert node_map["py1"].rows == 2


def test_executor_syntax_error_fails_node(tmp_path: Path, sample_csv: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "py1",
                "type": "pythonTransform",
                # validate_config catches this at graph-save time; at execute time
                # the script was already validated so syntax errors come from exec.
                "data": {"config": {"script": "return df[df['a'] > 1]"}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "py1"},
            {"id": "e2", "source": "py1", "target": "out1"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir)
    assert result.error is None  # valid script succeeds


def test_executor_none_return_fails_run(tmp_path: Path, sample_csv: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "py1",
                "type": "pythonTransform",
                "data": {"config": {"script": "result = df  # no return"}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "py1"},
            {"id": "e2", "source": "py1", "target": "out1"},
        ],
    }
    result = FlowExecutor().run_with_results(graph, _paths(ds1=sample_csv), out_dir)
    assert result.error is not None
    node_map = {r.node_id: r for r in result.node_results}
    assert node_map["py1"].status == "failed"
    assert node_map["out1"].status == "skipped"
