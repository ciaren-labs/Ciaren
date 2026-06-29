"""Behavior + edge-case coverage for the free-tier nodes added on top of the
core ETL set: filterExpression, combineColumns, coalesceColumns, explodeRows,
rollingAggregate, rowDifference, dateDifference, assertValuesInSet.

Every behavioral test runs on **both** engines (pandas and polars) so the two
backends stay in lockstep; codegen for both generators is compiled (and, where it
matters, executed) so the exported scripts stay runnable.
"""

import math

import numpy as np
import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.registry import get_transformation
from app.engine.transformations.quality import AssertionViolationError


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def run(engine, node_type, pdf, config):
    """validate + execute a node, returning the result as a pandas frame."""
    node = get_transformation(node_type)
    node.validate_config(config)
    out = node.execute(engine, {"in": _native(engine, pdf)}, config)
    return engine.to_pandas(out["out"])


def compiles(node_type, config):
    node = get_transformation(node_type)
    header = "import pandas as pd\nimport polars as pl\n"
    for meth in ("to_python_code", "to_polars_code"):
        code = getattr(node, meth)({"in": "df"}, {"out": "result"}, config)
        compile(header + code, "<gen>", "exec")


# ===========================================================================
# filterExpression
# ===========================================================================


class TestFilterExpression:
    def test_basic_and_expression(self, engine):
        df = pd.DataFrame({"amount": [10, 150, 200, 50], "status": ["paid", "pending", "paid", "paid"]})
        out = run(engine, "filterExpression", df, {"expression": "amount > 100 and status == 'paid'"})
        assert out["amount"].tolist() == [200]

    def test_all_rows_match(self, engine):
        df = pd.DataFrame({"a": [1, 2, 3]})
        out = run(engine, "filterExpression", df, {"expression": "a > 0"})
        assert len(out) == 3

    def test_no_rows_match_returns_empty(self, engine):
        df = pd.DataFrame({"a": [1, 2, 3]})
        out = run(engine, "filterExpression", df, {"expression": "a > 100"})
        assert len(out) == 0
        assert list(out.columns) == ["a"]  # schema preserved on an empty result

    def test_index_is_reset(self, engine):
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        out = run(engine, "filterExpression", df, {"expression": "a % 2 == 0"})
        # rows 2 and 4 survive; index must be 0,1 (not 1,3) so downstream .loc works.
        assert out.index.tolist() == [0, 1]
        assert out["a"].tolist() == [2, 4]

    def test_both_engines_agree(self):
        df = pd.DataFrame({"a": [1, 5, 9, 13], "b": [10, 20, 30, 40]})
        cfg = {"expression": "a > 4 and b < 40"}
        p = run(get_engine("pandas"), "filterExpression", df, cfg)["a"].tolist()
        q = run(get_engine("polars"), "filterExpression", df, cfg)["a"].tolist()
        assert p == q == [5, 9]

    def test_empty_expression_rejected(self):
        node = get_transformation("filterExpression")
        with pytest.raises(ValueError, match="expression"):
            node.validate_config({"expression": "   "})

    def test_codegen_compiles(self):
        compiles("filterExpression", {"expression": "a > 1 and b == 'x'"})


# ===========================================================================
# combineColumns
# ===========================================================================


class TestCombineColumns:
    def test_basic_join(self, engine):
        df = pd.DataFrame({"first": ["John", "Jane"], "last": ["Doe", "Roe"]})
        out = run(engine, "combineColumns", df, {"columns": ["first", "last"], "new_column": "full", "separator": " "})
        assert out["full"].tolist() == ["John Doe", "Jane Roe"]

    def test_null_becomes_empty_separator_preserved(self, engine):
        # Edge case: a null cell becomes "" but the separator is still emitted, so
        # the field's position is preserved ("a||c", not "a|c").
        df = pd.DataFrame({"a": ["a", "x"], "b": [None, "y"], "c": ["c", "z"]})
        out = run(engine, "combineColumns", df, {"columns": ["a", "b", "c"], "new_column": "j", "separator": "|"})
        assert out["j"].tolist() == ["a||c", "x|y|z"]

    def test_keep_original_false_drops_sources(self, engine):
        df = pd.DataFrame({"a": ["1"], "b": ["2"], "keep": ["k"]})
        out = run(engine, "combineColumns", df, {"columns": ["a", "b"], "new_column": "c", "keep_original": False})
        assert "a" not in out.columns and "b" not in out.columns
        assert out["keep"].tolist() == ["k"] and out["c"].tolist() == ["1 2"]

    def test_numeric_columns_are_stringified(self, engine):
        df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
        out = run(engine, "combineColumns", df, {"columns": ["x", "y"], "new_column": "xy", "separator": "-"})
        assert out["xy"].tolist() == ["1-3", "2-4"]

    def test_requires_two_columns(self):
        node = get_transformation("combineColumns")
        with pytest.raises(ValueError, match="two columns"):
            node.validate_config({"columns": ["a"], "new_column": "c"})

    def test_requires_new_column(self):
        node = get_transformation("combineColumns")
        with pytest.raises(ValueError, match="new_column"):
            node.validate_config({"columns": ["a", "b"]})

    def test_codegen_compiles(self):
        compiles("combineColumns", {"columns": ["a", "b"], "new_column": "c", "separator": "-", "keep_original": False})


# ===========================================================================
# coalesceColumns
# ===========================================================================


class TestCoalesceColumns:
    def test_first_non_null_wins(self, engine):
        df = pd.DataFrame({"a": [None, "y", None], "b": ["B", "x", None], "c": ["C", "z", "Z"]})
        out = run(engine, "coalesceColumns", df, {"columns": ["a", "b", "c"], "new_column": "first"})
        assert out["first"].tolist() == ["B", "y", "Z"]

    def test_all_null_row_yields_null(self, engine):
        df = pd.DataFrame({"a": [None, "x"], "b": [None, "y"]})
        out = run(engine, "coalesceColumns", df, {"columns": ["a", "b"], "new_column": "c"})
        assert out["c"].isna().tolist() == [True, False]

    def test_keep_original_false_drops_sources(self, engine):
        df = pd.DataFrame({"a": [None], "b": ["v"], "other": ["o"]})
        out = run(engine, "coalesceColumns", df, {"columns": ["a", "b"], "new_column": "r", "keep_original": False})
        assert set(out.columns) == {"other", "r"}
        assert out["r"].tolist() == ["v"]

    def test_requires_two_columns(self):
        node = get_transformation("coalesceColumns")
        with pytest.raises(ValueError, match="two columns"):
            node.validate_config({"columns": ["a"], "new_column": "c"})

    def test_codegen_compiles(self):
        compiles("coalesceColumns", {"columns": ["a", "b"], "new_column": "c", "keep_original": False})


# ===========================================================================
# explodeRows
# ===========================================================================


class TestExplodeRows:
    def test_delimiter_split(self, engine):
        df = pd.DataFrame({"id": [1, 2], "tags": ["x;y", "p;q;r"]})
        out = run(engine, "explodeRows", df, {"column": "tags", "delimiter": ";"})
        assert out["tags"].tolist() == ["x", "y", "p", "q", "r"]
        assert out["id"].tolist() == [1, 1, 2, 2, 2]  # id repeats per exploded value

    def test_single_value_without_delimiter_present(self, engine):
        # A cell with no delimiter explodes to a single row (count unchanged).
        df = pd.DataFrame({"tags": ["solo", "a;b"]})
        out = run(engine, "explodeRows", df, {"column": "tags", "delimiter": ";"})
        assert out["tags"].tolist() == ["solo", "a", "b"]

    def test_trailing_delimiter_yields_empty_value(self, engine):
        df = pd.DataFrame({"tags": ["a;"]})
        out = run(engine, "explodeRows", df, {"column": "tags", "delimiter": ";"})
        assert out["tags"].tolist() == ["a", ""]

    def test_list_column_without_delimiter(self, engine):
        # No delimiter: an existing list column is exploded directly.
        df = pd.DataFrame({"id": [1, 2], "vals": [[10, 20], [30]]})
        out = run(engine, "explodeRows", df, {"column": "vals", "delimiter": ""})
        assert out["vals"].tolist() == [10, 20, 30]
        assert out["id"].tolist() == [1, 1, 2]

    def test_index_reset(self, engine):
        df = pd.DataFrame({"tags": ["a;b;c"]})
        out = run(engine, "explodeRows", df, {"column": "tags", "delimiter": ";"})
        assert out.index.tolist() == [0, 1, 2]

    def test_requires_column(self):
        node = get_transformation("explodeRows")
        with pytest.raises(ValueError, match="column"):
            node.validate_config({"delimiter": ";"})

    def test_codegen_compiles(self):
        compiles("explodeRows", {"column": "tags", "delimiter": ";"})
        compiles("explodeRows", {"column": "vals"})  # no-delimiter branch


# ===========================================================================
# rollingAggregate
# ===========================================================================


class TestRollingAggregate:
    def test_moving_mean_ordered(self, engine):
        df = pd.DataFrame({"t": [1, 2, 3, 4], "v": [10.0, 20.0, 30.0, 40.0]})
        out = run(
            engine,
            "rollingAggregate",
            df,
            {"target": "v", "function": "mean", "window": 2, "order_by": ["t"], "new_column": "ma"},
        )
        out = out.sort_values("t")
        # window=2, min_periods defaults to window → first row is null.
        assert math.isnan(out["ma"].iloc[0])
        assert out["ma"].tolist()[1:] == [15.0, 25.0, 35.0]

    def test_min_periods_allows_partial_window(self, engine):
        df = pd.DataFrame({"t": [1, 2, 3], "v": [10.0, 20.0, 30.0]})
        out = run(
            engine,
            "rollingAggregate",
            df,
            {"target": "v", "function": "mean", "window": 2, "min_periods": 1, "order_by": ["t"], "new_column": "ma"},
        ).sort_values("t")
        # min_periods=1 → first row is its own value, not null.
        assert out["ma"].tolist() == [10.0, 15.0, 25.0]

    def test_partition_resets_window(self, engine):
        df = pd.DataFrame(
            {"g": ["a", "a", "b", "b"], "t": [1, 2, 1, 2], "v": [1.0, 3.0, 10.0, 30.0]}
        )
        out = run(
            engine,
            "rollingAggregate",
            df,
            {
                "target": "v",
                "function": "sum",
                "window": 2,
                "min_periods": 1,
                "partition_by": ["g"],
                "order_by": ["t"],
                "new_column": "rs",
            },
        ).sort_values(["g", "t"])
        # Each group's window is independent: a→[1,4], b→[10,40].
        assert out["rs"].tolist() == [1.0, 4.0, 10.0, 40.0]

    def test_preserves_original_row_order(self, engine):
        # Input is NOT pre-sorted by the order key; output keeps input order.
        df = pd.DataFrame({"t": [3, 1, 2], "v": [30.0, 10.0, 20.0]})
        out = run(
            engine,
            "rollingAggregate",
            df,
            {"target": "v", "function": "mean", "window": 2, "min_periods": 1, "order_by": ["t"], "new_column": "ma"},
        )
        # Row order matches input (t=3,1,2). For t=3 (last in time) window=[20,30]→25.
        assert out["t"].tolist() == [3, 1, 2]
        assert out["ma"].tolist() == [25.0, 10.0, 15.0]

    @pytest.mark.parametrize("func", ["mean", "sum", "min", "max", "std", "median"])
    def test_all_functions_run(self, engine, func):
        df = pd.DataFrame({"t": [1, 2, 3, 4], "v": [1.0, 2.0, 3.0, 4.0]})
        out = run(
            engine,
            "rollingAggregate",
            df,
            {"target": "v", "function": func, "window": 2, "min_periods": 1, "order_by": ["t"], "new_column": "r"},
        )
        assert "r" in out.columns

    def test_invalid_function_rejected(self):
        node = get_transformation("rollingAggregate")
        with pytest.raises(ValueError, match="function"):
            node.validate_config({"target": "v", "function": "variance", "window": 2, "new_column": "r"})

    def test_invalid_window_rejected(self):
        node = get_transformation("rollingAggregate")
        with pytest.raises(ValueError, match="window"):
            node.validate_config({"target": "v", "function": "mean", "window": 0, "new_column": "r"})

    def test_codegen_compiles(self):
        cfg = {"target": "v", "function": "mean", "window": 3}
        cfg.update({"partition_by": ["g"], "order_by": ["t"], "new_column": "r"})
        compiles("rollingAggregate", cfg)


# ===========================================================================
# rowDifference
# ===========================================================================


class TestRowDifference:
    def test_diff(self, engine):
        df = pd.DataFrame({"t": [1, 2, 3], "v": [10.0, 14.0, 9.0]})
        out = run(
            engine, "rowDifference", df, {"target": "v", "method": "diff", "order_by": ["t"], "new_column": "d"}
        ).sort_values("t")
        assert math.isnan(out["d"].iloc[0])
        assert out["d"].tolist()[1:] == [4.0, -5.0]

    def test_pct_change(self, engine):
        df = pd.DataFrame({"t": [1, 2, 3], "v": [100.0, 150.0, 75.0]})
        out = run(
            engine, "rowDifference", df, {"target": "v", "method": "pct_change", "order_by": ["t"], "new_column": "p"}
        ).sort_values("t")
        assert out["p"].tolist()[1:] == [0.5, -0.5]

    def test_periods_greater_than_one(self, engine):
        df = pd.DataFrame({"t": [1, 2, 3, 4], "v": [1.0, 2.0, 4.0, 8.0]})
        out = run(
            engine,
            "rowDifference",
            df,
            {"target": "v", "method": "diff", "periods": 2, "order_by": ["t"], "new_column": "d"},
        ).sort_values("t")
        # diff(2): row3 = 4-1 = 3, row4 = 8-2 = 6; first two are null.
        assert out["d"].tolist()[2:] == [3.0, 6.0]

    def test_partition_isolation(self, engine):
        df = pd.DataFrame({"g": ["a", "a", "b", "b"], "t": [1, 2, 1, 2], "v": [1.0, 5.0, 100.0, 130.0]})
        out = run(
            engine,
            "rowDifference",
            df,
            {"target": "v", "method": "diff", "partition_by": ["g"], "order_by": ["t"], "new_column": "d"},
        ).sort_values(["g", "t"])
        # First row of each group is null; no diff bleeds across the group boundary.
        diffs = out["d"].tolist()
        assert math.isnan(diffs[0]) and diffs[1] == 4.0
        assert math.isnan(diffs[2]) and diffs[3] == 30.0

    def test_invalid_method_rejected(self):
        node = get_transformation("rowDifference")
        with pytest.raises(ValueError, match="method"):
            node.validate_config({"target": "v", "method": "delta", "new_column": "d"})

    def test_invalid_periods_rejected(self):
        node = get_transformation("rowDifference")
        with pytest.raises(ValueError, match="periods"):
            node.validate_config({"target": "v", "periods": 0, "new_column": "d"})

    def test_codegen_compiles(self):
        cfg = {"target": "v", "method": "pct_change", "periods": 1}
        cfg.update({"partition_by": ["g"], "order_by": ["t"], "new_column": "d"})
        compiles("rowDifference", cfg)


# ===========================================================================
# dateDifference
# ===========================================================================


class TestDateDifference:
    def test_days(self, engine):
        df = pd.DataFrame({"start": ["2024-01-01", "2024-02-01"], "end": ["2024-01-11", "2024-02-15"]})
        out = run(
            engine,
            "dateDifference",
            df,
            {"start_column": "start", "end_column": "end", "unit": "days", "new_column": "span"},
        )
        assert out["span"].tolist() == [10.0, 14.0]

    @pytest.mark.parametrize("unit,expected", [("hours", 24.0), ("minutes", 1440.0), ("weeks", 1.0 / 7.0)])
    def test_units(self, engine, unit, expected):
        df = pd.DataFrame({"start": ["2024-01-01"], "end": ["2024-01-02"]})  # exactly one day apart
        out = run(
            engine,
            "dateDifference",
            df,
            {"start_column": "start", "end_column": "end", "unit": unit, "new_column": "d"},
        )
        assert out["d"].iloc[0] == pytest.approx(expected)

    def test_negative_when_end_before_start(self, engine):
        df = pd.DataFrame({"start": ["2024-01-10"], "end": ["2024-01-05"]})
        out = run(
            engine,
            "dateDifference",
            df,
            {"start_column": "start", "end_column": "end", "unit": "days", "new_column": "d"},
        )
        assert out["d"].iloc[0] == -5.0

    def test_invalid_date_becomes_null(self, engine):
        df = pd.DataFrame({"start": ["not-a-date", "2024-01-01"], "end": ["2024-01-05", "2024-01-03"]})
        out = run(
            engine,
            "dateDifference",
            df,
            {"start_column": "start", "end_column": "end", "unit": "days", "new_column": "d"},
        )
        assert math.isnan(out["d"].iloc[0])  # unparseable date → null, not a crash
        assert out["d"].iloc[1] == 2.0

    def test_invalid_unit_rejected(self):
        node = get_transformation("dateDifference")
        with pytest.raises(ValueError, match="unit"):
            node.validate_config({"start_column": "a", "end_column": "b", "unit": "months", "new_column": "d"})

    def test_missing_columns_rejected(self):
        node = get_transformation("dateDifference")
        with pytest.raises(ValueError, match="end_column"):
            node.validate_config({"start_column": "a", "unit": "days", "new_column": "d"})

    def test_codegen_compiles(self):
        compiles("dateDifference", {"start_column": "a", "end_column": "b", "unit": "hours", "new_column": "d"})


# ===========================================================================
# assertValuesInSet
# ===========================================================================


def _assert_meta(engine, pdf, config):
    node = get_transformation("assertValuesInSet")
    node.validate_config(config)
    frames, meta = node.execute_with_metadata(engine, {"in": _native(engine, pdf)}, config)
    return engine.to_pandas(frames["out"]), meta


class TestAssertValuesInSet:
    def test_passes_when_all_in_set(self, engine):
        df = pd.DataFrame({"status": ["paid", "pending", "paid"]})
        out, meta = _assert_meta(engine, df, {"column": "status", "allowed": ["paid", "pending", "failed"]})
        assert meta.assertion_passed is True
        assert meta.assertion_violation_count == 0
        assert out["status"].tolist() == ["paid", "pending", "paid"]  # pass-through

    def test_raises_in_error_mode(self, engine):
        df = pd.DataFrame({"status": ["paid", "bogus"]})
        node = get_transformation("assertValuesInSet")
        cfg = {"column": "status", "allowed": ["paid"], "mode": "error"}
        with pytest.raises(AssertionViolationError, match="outside"):
            node.execute(engine, {"in": _native(engine, df)}, cfg)

    def test_warn_mode_records_violation(self, engine):
        df = pd.DataFrame({"status": ["paid", "bogus", "nope"]})
        out, meta = _assert_meta(engine, df, {"column": "status", "allowed": ["paid"], "mode": "warn"})
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 2
        assert len(out) == 3  # warn mode does not drop rows

    def test_null_allowed_by_default(self, engine):
        df = pd.DataFrame({"status": ["paid", None]})
        _out, meta = _assert_meta(engine, df, {"column": "status", "allowed": ["paid"], "mode": "warn"})
        assert meta.assertion_passed is True  # null tolerated when allow_null defaults True

    def test_null_disallowed_when_allow_null_false(self, engine):
        df = pd.DataFrame({"status": ["paid", None]})
        _out, meta = _assert_meta(
            engine, df, {"column": "status", "allowed": ["paid"], "allow_null": False, "mode": "warn"}
        )
        assert meta.assertion_passed is False
        assert meta.assertion_violation_count == 1

    def test_empty_allowed_rejected(self):
        node = get_transformation("assertValuesInSet")
        with pytest.raises(ValueError, match="allowed"):
            node.validate_config({"column": "status", "allowed": []})

    def test_missing_column_at_runtime(self, engine):
        df = pd.DataFrame({"status": ["paid"]})
        node = get_transformation("assertValuesInSet")
        with pytest.raises(ValueError, match="not found"):
            node.execute(engine, {"in": _native(engine, df)}, {"column": "ghost", "allowed": ["x"]})

    def test_codegen_compiles(self):
        compiles("assertValuesInSet", {"column": "status", "allowed": ["a", "b"], "mode": "warn"})
        compiles("assertValuesInSet", {"column": "status", "allowed": ["a"], "allow_null": False, "mode": "error"})


# ===========================================================================
# Generated code actually runs (not just compiles)
# ===========================================================================


def test_generated_pandas_code_runs_combine():
    df = pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]})
    code = get_transformation("combineColumns").to_python_code(
        {"in": "df"}, {"out": "result"}, {"columns": ["a", "b"], "new_column": "c", "separator": "-"}
    )
    ns = {"pd": pd, "df": df.copy()}
    exec(code, ns)
    assert ns["result"]["c"].tolist() == ["1-x", "2-y"]


def test_generated_polars_code_runs_rowdiff():
    df = pl.DataFrame({"t": [1, 2, 3], "v": [10.0, 13.0, 9.0]})
    code = get_transformation("rowDifference").to_polars_code(
        {"in": "df"}, {"out": "result"}, {"target": "v", "method": "diff", "order_by": ["t"], "new_column": "d"}
    )
    ns = {"pl": pl, "df": df.clone()}
    exec(code, ns)
    assert ns["result"]["d"].to_list()[1:] == [3.0, -4.0]


def test_generated_pandas_code_runs_datediff():
    df = pd.DataFrame({"s": ["2024-01-01"], "e": ["2024-01-04"]})
    code = get_transformation("dateDifference").to_python_code(
        {"in": "df"}, {"out": "result"}, {"start_column": "s", "end_column": "e", "unit": "days", "new_column": "d"}
    )
    ns = {"pd": pd, "np": np, "df": df.copy()}
    exec(code, ns)
    assert ns["result"]["d"].tolist() == [3.0]
