"""Polars code generation: the script must be valid Python and use polars APIs."""

import subprocess
import sys
from pathlib import Path

import pandas as pd

from app.engine.polars_codegen import PolarsCodeGenerator


def _wide_graph(dataset_id: str = "ds1") -> dict:
    """An input feeding a chain that exercises many node types."""
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "ren", "type": "renameColumns", "data": {"config": {"mapping": {"a": "alpha"}}}},
            {
                "id": "flt",
                "type": "filterRows",
                "data": {"config": {"column": "alpha", "operator": ">", "value": 1}},
            },
            {
                "id": "calc",
                "type": "calculatedColumn",
                "data": {"config": {"column_name": "x2", "expression": "alpha * 2"}},
            },
            {
                "id": "grp",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["alpha"], "aggregations": {"x2": "sum"}}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "ren"},
            {"id": "e3", "source": "ren", "target": "flt"},
            {"id": "e4", "source": "flt", "target": "calc"},
            {"id": "e5", "source": "calc", "target": "grp"},
            {"id": "e6", "source": "grp", "target": "out"},
        ],
    }


def test_polars_codegen_is_valid_and_uses_polars() -> None:
    code = PolarsCodeGenerator().generate(_wide_graph(), {"ds1": "/data/in.csv"})
    assert code.startswith("import polars as pl")
    assert 'pl.read_csv("/data/in.csv")' in code
    assert ".drop_nulls()" in code
    assert ".rename({'a': 'alpha'})" in code
    assert ".filter(pl.col('alpha') > 1)" in code
    assert "pl.sql_expr('alpha * 2').alias('x2')" in code
    assert ".group_by(['alpha']).agg(" in code
    assert ".write_csv(" in code
    compile(code, "<generated-polars>", "exec")


def test_polars_codegen_fill_strategy_and_filter_ops() -> None:
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "fill",
                "type": "fillNulls",
                "data": {"config": {"strategy": "mean", "columns": ["a"]}},
            },
            {
                "id": "flt",
                "type": "filterRows",
                "data": {"config": {"column": "a", "operator": "between", "value": 1, "value2": 9}},
            },
            {
                "id": "flt2",
                "type": "filterRows",
                "data": {"config": {"column": "b", "operator": "in", "value": "x, y"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "fill"},
            {"id": "e2", "source": "fill", "target": "flt"},
            {"id": "e3", "source": "flt", "target": "flt2"},
            {"id": "e4", "source": "flt2", "target": "out"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"ds1": "in.csv"})
    assert "fill_null(strategy='mean')" in code
    assert ".is_between(1, 9)" in code
    assert ".is_in(['x', 'y'])" in code
    compile(code, "<generated-polars-fill>", "exec")


def test_polars_join_and_concat() -> None:
    graph = {
        "nodes": [
            {"id": "l", "type": "csvInput", "data": {"config": {"dataset_id": "L"}}},
            {"id": "r", "type": "csvInput", "data": {"config": {"dataset_id": "R"}}},
            {"id": "j", "type": "join", "data": {"config": {"on": "id", "how": "outer"}}},
            {"id": "o", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "l", "target": "j", "targetHandle": "left"},
            {"id": "e2", "source": "r", "target": "j", "targetHandle": "right"},
            {"id": "e3", "source": "j", "target": "o"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"L": "l.csv", "R": "r.csv"})
    assert ".join(" in code
    assert "how='full'" in code  # pandas 'outer' maps to polars 'full'
    compile(code, "<generated-polars-join>", "exec")


# --- lazy mode -------------------------------------------------------------


def _run(code: str, tmp_path: Path) -> pd.DataFrame:
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, f"generated script failed:\n{result.stderr}"
    return pd.read_csv(tmp_path / "out.csv")


def test_polars_lazy_uses_scan_and_collect() -> None:
    code = PolarsCodeGenerator().generate(_wide_graph(), {"ds1": "/data/in.csv"}, lazy=True)
    assert 'pl.scan_csv("/data/in.csv")' in code  # lazy reader, not read_csv
    assert "pl.read_csv" not in code
    assert ".collect().write_csv(" in code  # materialize only at the sink
    assert ".drop_nulls()" in code  # transformation bodies are unchanged
    assert ".group_by(['alpha']).agg(" in code
    compile(code, "<lazy-polars>", "exec")


def _pivot_graph() -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {
                "id": "pv",
                "type": "pivot",
                "data": {"config": {"index": "region", "columns": "product", "values": "amount", "aggfunc": "sum"}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "pv"},
            {"id": "e2", "source": "pv", "target": "out"},
        ],
    }


def test_polars_lazy_materializes_eager_only_pivot() -> None:
    code = PolarsCodeGenerator().generate(_pivot_graph(), {"ds1": "in.csv"}, lazy=True)
    # pivot has no lazy form: collect into eager, pivot, then re-enter the plan.
    assert "# pivot has no lazy equivalent" in code
    assert ".collect()" in code
    assert ".pivot(" in code
    assert "_eager_2.lazy()" in code
    compile(code, "<lazy-pivot>", "exec")


def test_polars_lazy_materializes_eager_only_sample() -> None:
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "s", "type": "sampleRows", "data": {"config": {"n": 1, "seed": 7}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "s"},
            {"id": "e2", "source": "s", "target": "out"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"ds1": "in.csv"}, lazy=True)
    assert "# sampleRows has no lazy equivalent" in code
    assert ".sample(n=1, seed=7)" in code
    assert ".lazy()" in code
    compile(code, "<lazy-sample>", "exec")


def test_polars_lazy_runs_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "in.csv").write_text("region,product,amount\nN,x,2\nN,y,3\nS,x,5\n")
    graph = {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "flt", "type": "filterRows", "data": {"config": {"column": "amount", "operator": ">", "value": 2}}},
            {
                "id": "grp",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["region"], "aggregations": {"amount": "sum"}}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "flt"},
            {"id": "e2", "source": "flt", "target": "grp"},
            {"id": "e3", "source": "grp", "target": "out"},
        ],
    }
    code = PolarsCodeGenerator().generate(graph, {"ds1": "in.csv"}, lazy=True)
    out = _run(code, tmp_path)
    totals = dict(zip(out["region"], out["amount"]))
    assert totals == {"N": 3, "S": 5}  # amount>2 keeps N/y=3 and S/x=5


def test_polars_lazy_pivot_runs_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "in.csv").write_text("region,product,amount\nN,x,2\nN,y,3\nS,x,5\n")
    graph = _pivot_graph()
    code = PolarsCodeGenerator().generate(graph, {"ds1": "in.csv"}, lazy=True)
    out = _run(code, tmp_path)
    by_region = {row["region"]: row for _, row in out.iterrows()}
    assert by_region["N"]["x"] == 2
    assert by_region["N"]["y"] == 3
    assert by_region["S"]["x"] == 5
