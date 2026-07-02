"""`free_intermediates` (del) correctness for the pandas and eager-polars exports.

The risk with emitting ``del`` is freeing a dataframe *before* a later node
still needs it. We guard that two ways on deliberately tricky graphs (fan-out,
a late multi-input join chain):

1. **Static** — no variable is ever referenced after its ``del``.
2. **Runtime** — the generated script is ``exec``'d against real CSVs; an early
   ``del`` would raise ``NameError`` (or corrupt the result), so a correct
   output proves nothing was freed too soon.
"""

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from app.engine.codegen import CodeGenerator
from app.engine.polars_codegen import PolarsCodeGenerator

_VAR = re.compile(r"\bdf_\d+\b")


def assert_no_use_after_del(code: str) -> None:
    deleted_at: dict[str, int] = {}
    for i, raw in enumerate(code.splitlines()):
        line = raw.strip()
        m = re.fullmatch(r"del (df_\d+)", line)
        if m:
            deleted_at[m.group(1)] = i
            continue
        for var in _VAR.findall(line):
            assert var not in deleted_at, (
                f"{var} used on line {i} ({line!r}) after it was deleted on line {deleted_at[var]}"
            )


def _del_count(code: str) -> int:
    return sum(1 for line in code.splitlines() if line.strip().startswith("del "))


def _run(code: str, tmp_path: Path) -> pd.DataFrame:
    """Execute a generated script in a clean subprocess and load its output CSV."""
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"generated script failed:\n{result.stderr}"
    return pd.read_csv(tmp_path / "out.csv")


# --- a late multi-input join chain (inputs must survive far past their read) ---


def _multi_join_graph(out_path: str) -> dict:
    return {
        "nodes": [
            {"id": "oi", "type": "csvInput", "data": {"config": {"dataset_id": "order_items"}}},
            {"id": "pr", "type": "csvInput", "data": {"config": {"dataset_id": "products"}}},
            {"id": "ord", "type": "csvInput", "data": {"config": {"dataset_id": "orders"}}},
            {
                "id": "calc",
                "type": "calculatedColumn",
                "data": {"config": {"column_name": "line_total", "expression": "quantity * unit_price"}},
            },
            {"id": "j1", "type": "join", "data": {"config": {"on": "product_id", "how": "left"}}},
            {"id": "j2", "type": "join", "data": {"config": {"on": "order_id", "how": "left"}}},
            {
                "id": "grp",
                "type": "groupByAggregate",
                "data": {"config": {"group_by": ["category"], "aggregations": {"line_total": "sum"}}},
            },
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": out_path}}},
        ],
        "edges": [
            {"id": "e1", "source": "oi", "target": "calc"},
            {"id": "e2", "source": "calc", "target": "j1", "targetHandle": "left"},
            {"id": "e3", "source": "pr", "target": "j1", "targetHandle": "right"},
            {"id": "e4", "source": "j1", "target": "j2", "targetHandle": "left"},
            {"id": "e5", "source": "ord", "target": "j2", "targetHandle": "right"},
            {"id": "e6", "source": "j2", "target": "grp"},
            {"id": "e7", "source": "grp", "target": "out"},
        ],
    }


def _write_join_inputs(tmp_path: Path) -> dict[str, str]:
    # Bare filenames: the script runs with cwd=tmp_path, mirroring how the real
    # export references portable dataset filenames rather than absolute paths.
    (tmp_path / "order_items.csv").write_text(
        "order_id,product_id,quantity,unit_price\n1,10,2,5.0\n1,11,1,3.0\n2,10,3,5.0\n"
    )
    (tmp_path / "products.csv").write_text("product_id,category\n10,A\n11,B\n")
    (tmp_path / "orders.csv").write_text("order_id,region\n1,north\n2,south\n")
    return {
        "order_items": "order_items.csv",
        "products": "products.csv",
        "orders": "orders.csv",
    }


def _assert_join_output(df: pd.DataFrame) -> None:
    totals = dict(zip(df["category"], df["line_total"]))
    assert totals["A"] == 25.0  # 2*5 + 3*5
    assert totals["B"] == 3.0  # 1*3


def test_pandas_multi_join_del_is_safe(tmp_path: Path) -> None:
    paths = _write_join_inputs(tmp_path)
    graph = _multi_join_graph("out.csv")
    code = CodeGenerator().generate(graph, paths, free_intermediates=True)

    assert_no_use_after_del(code)
    # calc reuses order_items' variable and grp reuses j2's, leaving four dead
    # intermediates: both join inputs die at j1/j2 respectively.
    assert _del_count(code) == 4
    assert "del df_1" in code  # order_items (reused by calc), dead after j1

    _assert_join_output(_run(code, tmp_path))


def test_polars_multi_join_del_is_safe(tmp_path: Path) -> None:
    paths = _write_join_inputs(tmp_path)
    graph = _multi_join_graph("out.csv")
    code = PolarsCodeGenerator().generate(graph, paths, free_intermediates=True)

    assert_no_use_after_del(code)
    assert _del_count(code) == 4
    _assert_join_output(_run(code, tmp_path))


# --- fan-out: one input consumed by two branches that later re-converge ---


def _diamond_graph(out_path: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "people"}}},
            {"id": "fa", "type": "filterRows", "data": {"config": {"column": "age", "operator": ">", "value": 25}}},
            {"id": "fb", "type": "filterRows", "data": {"config": {"column": "age", "operator": "<=", "value": 25}}},
            {"id": "cat", "type": "concatRows", "data": {"config": {}}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": out_path}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "fa"},
            {"id": "e2", "source": "in1", "target": "fb"},
            {"id": "e3", "source": "fa", "target": "cat"},
            {"id": "e4", "source": "fb", "target": "cat"},
            {"id": "e5", "source": "cat", "target": "out"},
        ],
    }


def _write_people(tmp_path: Path) -> dict[str, str]:
    (tmp_path / "people.csv").write_text("name,age\nAlice,30\nBob,20\nCarol,25\n")
    return {"people": "people.csv"}


def test_pandas_fanout_input_not_freed_before_second_branch(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    graph = _diamond_graph("out.csv")
    code = CodeGenerator().generate(graph, paths, free_intermediates=True)

    assert_no_use_after_del(code)
    # in1 (df_1) feeds both filters; the second one takes the variable over, so
    # its del (now holding that branch's result) must come after both filters.
    del_line = next(i for i, ln in enumerate(code.splitlines()) if ln.strip() == "del df_1")
    filter_lines = [i for i, ln in enumerate(code.splitlines()) if ".isin" in ln or "[df_1[" in ln]
    assert del_line > max(filter_lines)

    out = _run(code, tmp_path)
    assert len(out) == 3  # both branches preserved, nothing dropped early


def test_polars_fanout_input_not_freed_before_second_branch(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    graph = _diamond_graph("out.csv")
    code = PolarsCodeGenerator().generate(graph, paths, free_intermediates=True)

    assert_no_use_after_del(code)
    out = _run(code, tmp_path)
    assert len(out) == 3


def test_off_by_default_no_del(tmp_path: Path) -> None:
    paths = _write_people(tmp_path)
    graph = _diamond_graph("out.csv")
    for code in (
        CodeGenerator().generate(graph, paths),
        PolarsCodeGenerator().generate(graph, paths),
    ):
        assert "del " not in code
