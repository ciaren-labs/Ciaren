# SPDX-License-Identifier: AGPL-3.0-only
"""Lazy-mode scripts must run for every node kind (regression for day-0 bugs).

Three bundled demo flows exported broken polars-lazy scripts: fillNulls
median/mode emitted series subscripts (``df[c].median()``), and the assertion
nodes, removeOutliers, and binColumn (equal-width) used ``.height`` / ``len()``
/ subscripts — none of which exist on a LazyFrame. fillNulls now emits pure
expressions (lazy-safe); the others are marked ``polars_lazy_safe = False`` so
the driver materializes around them.

Each case here generates the lazy script for a small input → node → output
flow and *runs* it, then compares the written CSV against the eager script's
output — shape-level equivalence between the two modes, not just "it didn't
crash".
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.engine.polars_codegen import PolarsCodeGenerator

# The default frame has a null in v (exercises the fill strategies); checks
# that treat nulls as violations (value range, eval expressions, all-numeric
# median) get the null-free / numeric-only frame instead.
_CSV_WITH_NULL = "id,g,v\n1,a,1.5\n2,b,\n3,a,2.5\n4,b,2.5\n5,a,50.0\n"
_CSV_NUMERIC = "id,v\n1,1.5\n2,2.0\n3,2.5\n4,2.5\n5,50.0\n"

CASES: dict[str, tuple[str, dict, str]] = {
    "fill_median": ("fillNulls", {"strategy": "median", "columns": ["v"]}, _CSV_WITH_NULL),
    "fill_median_all_cols": ("fillNulls", {"strategy": "median"}, _CSV_NUMERIC),
    "fill_mode": ("fillNulls", {"strategy": "mode", "columns": ["v"]}, _CSV_WITH_NULL),
    "fill_mean": ("fillNulls", {"strategy": "mean", "columns": ["v"]}, _CSV_WITH_NULL),
    "remove_outliers_iqr": ("removeOutliers", {"columns": ["v"], "method": "iqr", "action": "drop"}, _CSV_WITH_NULL),
    "remove_outliers_clip": (
        "removeOutliers",
        {"columns": ["v"], "method": "percentile", "action": "clip"},
        _CSV_WITH_NULL,
    ),
    "bin_equalwidth": (
        "binColumn",
        {"column": "v", "new_column": "band", "bins": 3, "method": "equalwidth"},
        _CSV_WITH_NULL,
    ),
    "bin_quantile": (
        "binColumn",
        {"column": "v", "new_column": "band", "bins": 3, "method": "quantile"},
        _CSV_WITH_NULL,
    ),
    "assert_not_null": ("assertNotNull", {"columns": ["g"]}, _CSV_WITH_NULL),
    "assert_unique": ("assertUnique", {"columns": ["id"]}, _CSV_WITH_NULL),
    "assert_value_range": ("assertValueRange", {"column": "v", "min": -100, "max": 100}, _CSV_NUMERIC),
    "assert_values_in_set": ("assertValuesInSet", {"column": "g", "allowed": ["a", "b"]}, _CSV_WITH_NULL),
    "assert_expression": ("assertExpression", {"expression": "v > -100"}, _CSV_NUMERIC),
    "assert_row_count": ("assertRowCount", {"min_rows": 1, "max_rows": 100}, _CSV_WITH_NULL),
    "drop_nulls_all": ("dropNulls", {"how": "all"}, _CSV_WITH_NULL),
}


def _graph(node_type: str, config: dict) -> dict:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "n", "type": node_type, "data": {"config": config}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "n"},
            {"id": "e2", "source": "n", "target": "out"},
        ],
    }


def _run(code: str, tmp_path: Path, tag: str) -> pd.DataFrame:
    script = tmp_path / f"script_{tag}.py"
    script.write_text(code, encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, f"lazy script failed:\n{result.stderr}\n---\n{code}"
    return pd.read_csv(tmp_path / "out.csv")


@pytest.mark.parametrize("case", CASES)
def test_lazy_script_runs_and_matches_eager(case: str, tmp_path: Path) -> None:
    node_type, config, csv = CASES[case]
    (tmp_path / "in.csv").write_text(csv)
    graph = _graph(node_type, config)
    gen = PolarsCodeGenerator()
    eager = _run(gen.generate(graph, {"d": "in.csv"}), tmp_path, "eager")
    lazy = _run(gen.generate(graph, {"d": "in.csv"}, lazy=True), tmp_path, "lazy")
    pd.testing.assert_frame_equal(eager, lazy)


@pytest.mark.parametrize(
    "case",
    ["fill_median_all_cols", "fill_mean", "drop_nulls_all"],
)
def test_lazy_scripts_emit_no_performance_warnings(case: str, tmp_path: Path) -> None:
    # LazyFrame.columns raises PerformanceWarning (and is slated for removal);
    # emitters iterate collect_schema().names() instead, so a lazy script runs
    # clean even with polars warnings promoted to errors.
    node_type, config, csv = CASES[case]
    (tmp_path / "in.csv").write_text(csv)
    code = PolarsCodeGenerator().generate(_graph(node_type, config), {"d": "in.csv"}, lazy=True)
    assert ".columns" not in code
    script = tmp_path / "script.py"
    script.write_text(code, encoding="utf-8")
    env = dict(os.environ, PYTHONWARNINGS="error::polars.exceptions.PerformanceWarning")
    result = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, env=env)
    assert result.returncode == 0, f"lazy script warned or failed:\n{result.stderr}\n---\n{code}"


def test_bin_quantile_stays_lazy_but_equalwidth_materializes() -> None:
    # Lazy safety is config-aware for binColumn: quantile is a pure .qcut()
    # expression and must not break the lazy plan; equal-width needs eager
    # min/max, so the driver materializes around it.
    gen = PolarsCodeGenerator()
    quantile = gen.generate(
        _graph("binColumn", {"column": "v", "new_column": "band", "bins": 3, "method": "quantile"}),
        {"d": "in.csv"},
        lazy=True,
    )
    assert "has no lazy equivalent" not in quantile
    assert "_eager_" not in quantile
    equalwidth = gen.generate(
        _graph("binColumn", {"column": "v", "new_column": "band", "bins": 3, "method": "equalwidth"}),
        {"d": "in.csv"},
        lazy=True,
    )
    assert "has no lazy equivalent" in equalwidth
    assert "_eager_" in equalwidth


def test_fill_mode_all_null_column_left_untouched(tmp_path: Path) -> None:
    # mode().first() on an all-null column is null; filling nulls with null is
    # a no-op — must not raise, in either mode (mirrors PolarsEngine).
    (tmp_path / "in.csv").write_text("id,v\n1,\n2,\n")
    graph = _graph("fillNulls", {"strategy": "mode", "columns": ["v"]})
    gen = PolarsCodeGenerator()
    eager = _run(gen.generate(graph, {"d": "in.csv"}), tmp_path, "eager")
    lazy = _run(gen.generate(graph, {"d": "in.csv"}, lazy=True), tmp_path, "lazy")
    assert eager["v"].isna().all()
    pd.testing.assert_frame_equal(eager, lazy)
