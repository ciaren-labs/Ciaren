"""Semantic equivalence between execute() and the generated code, per engine.

``test_transformation_codegen`` proves every emitter's output *compiles*; this
harness proves it computes the **same frame** as running the node through the
engine backend. For each ``CODEGEN_CASES`` entry we:

1. build suitable input frame(s),
2. run the node via ``execute`` on the pandas / polars backend,
3. ``exec`` the emitted pandas / polars source on the same inputs,
4. compare the results (order-insensitively where the op doesn't define order).

Every ``CODEGEN_CASES`` id must have an input-data entry here — a new codegen
branch cannot land without equivalence coverage (enforced by
``test_every_codegen_case_has_equivalence_data``).
"""

import io
from typing import Any

import pandas as pd
import polars as pl
import pytest
from pandas.testing import assert_frame_equal

from app.engine.backends.pandas_engine import PandasEngine
from app.engine.backends.polars_engine import PolarsEngine
from app.engine.registry import get_transformation
from tests.engine.test_transformation_codegen import CODEGEN_CASES

# --- input frames ------------------------------------------------------------


def _num() -> pd.DataFrame:
    """Numbers with decimals, a duplicate row, nulls, and one all-null row."""
    return pd.DataFrame(
        {
            "a": [1.0, 5.678, None, 9.999, 5.678, None],
            "b": [2.0, 4.0, 6.0, 8.0, 4.0, None],
        }
    )


def _text() -> pd.DataFrame:
    return pd.DataFrame({"a": ["x", "zebra", None, "yz", "x"], "b": [1, 2, 3, 4, 5]})


def _text_with_surrounding_spaces() -> pd.DataFrame:
    return pd.DataFrame({"a": ["  both  ", "left  ", "  right", None]})


def _dates_str() -> pd.DataFrame:
    return pd.DataFrame({"a": ["2024-01-02", "2024-03-04", None]})


def _dateparts_str() -> pd.DataFrame:
    return pd.DataFrame(
        {"a": ["2024-12-30 23:45", "2024-01-01 00:05", "2021-01-01 00:00", "2024-01-08 00:00", "not-a-date", None]}
    )


def _dateparts_dt() -> pd.DataFrame:
    return pd.DataFrame(
        {"d": pd.to_datetime(["2024-12-30 23:45", "2024-01-01 00:05", "2021-01-01 00:00", "2024-01-08 00:00", None])}
    )


def _datetimes() -> pd.DataFrame:
    return pd.DataFrame({"d": pd.to_datetime(["2024-01-02 03:04:05", "2023-12-31 23:59:59", "2024-06-15 12:00:00"])})


def _date_pair_str() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "s": ["2024-01-01 00:00:00", "2024-03-04 06:00:00", None],
            "e": ["2024-01-02 12:00:00", "2024-03-04 18:00:00", "2024-06-15 00:00:00"],
        }
    )


def _date_pair_dt() -> pd.DataFrame:
    # The same dates already parsed: upstream nodes often convert to datetime
    # before a date op runs, so its emitters must handle both dtypes.
    df = _date_pair_str()
    return df.assign(s=pd.to_datetime(df["s"]), e=pd.to_datetime(df["e"]))


def _ints_dirty() -> pd.DataFrame:
    return pd.DataFrame({"a": ["1", "x", "3"]})


def _single_col() -> pd.DataFrame:
    # rename_cols maps a -> b; the frame must not already have a 'b'.
    return pd.DataFrame({"a": [1.0, 2.0, None]})


def _all_null_float() -> pd.DataFrame:
    # 'n' has no median: both the engine and the emitted code must leave it
    # untouched instead of raising (float dtype so pandas treats it as numeric).
    return pd.DataFrame({"a": [1.0, None, 3.0], "n": pd.Series([None, None, None], dtype="float64")})


def _mixed_dtypes() -> pd.DataFrame:
    # A string column among numerics: mean/median fills must skip it (the app
    # engines do), not crash the exported script.
    return pd.DataFrame({"a": [1.0, None, 3.0], "s": ["x", None, "y"]})


def _with_empty_col() -> pd.DataFrame:
    # 'empty' has no mode: both engines and both emitted scripts must leave it
    # untouched (pandas mode().iloc[0] on an empty result is an IndexError).
    return pd.DataFrame({"a": [1.0, 1.0, None], "empty": pd.Series([None, None, None], dtype="float64")})


def _multimodal() -> pd.DataFrame:
    # Two modes (1.0 and 2.0): the fill must deterministically pick the
    # smallest on both engines (polars' mode order is random run to run).
    return pd.DataFrame({"a": [2.0, 2.0, 1.0, 1.0, None]})


def _text_special() -> pd.DataFrame:
    # "z.b" vs "zxb" separates regex from literal contains; "x5"/"5 stars"
    # exercise a numeric search value against stringified cells.
    return pd.DataFrame({"a": ["z.b", "zxb", "x5", None, "5 stars"]})


def _wide() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2], "x": [3.0, 4.0], "y": [5.0, 6.0]})


def _pivotable() -> pd.DataFrame:
    # 'v' carries a null so pivot aggfunc=count exercises non-null counting.
    return pd.DataFrame({"r": ["r1", "r1", "r2"], "c": ["c1", "c2", "c1"], "v": [1.0, None, 3.0]})


def _join_left() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2, 3], "lid": [1, 2, 3], "v": [10.0, 20.0, 30.0]})


def _join_right() -> pd.DataFrame:
    return pd.DataFrame({"id": [2, 3, 4], "rid": [2, 3, 4], "v": [7.0, 8.0, 9.0]})


def _join_membership_left() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": pd.Series([1, 2, 2, None, 3], dtype=object),
            "left_1": [1, 1, 2, 2, None],
            "left_2": ["x", "y", "x", None, "x"],
            "value": [10, 20, 30, 40, 50],
        }
    )


def _join_membership_right() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": pd.Series([2, 2, float("nan"), 4, 4], dtype=object),
            "right_1": [1, 1, 2, None, 4],
            "right_2": ["x", "x", None, "x", "z"],
            "right_value": [1, 2, 3, 4, 5],
        }
    )


def _join_incomplete_split_left() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "lid": [3, 1, 2],
            "value": [10, 20, 30],
        }
    )


def _join_incomplete_split_right() -> pd.DataFrame:
    return pd.DataFrame({"id": [2, 3], "right_value": [40, 50]})


def _grouped() -> pd.DataFrame:
    # Window/rolling/diff input: two partitions, scrambled tie-free order key,
    # and a null value so null propagation is exercised per engine.
    return pd.DataFrame(
        {
            "g": ["a", "b", "a", "b", "a"],
            "t": [3, 1, 1, 2, 2],
            "v": [10.0, 20.0, 30.0, None, 50.0],
        }
    )


def _csvish() -> pd.DataFrame:
    return pd.DataFrame({"a": ["x,y", "z", None], "b": [1, 2, 3]})


def _group_null_vals() -> pd.DataFrame:
    # Group keys with nulls in the aggregated column, including an all-null group
    # ('c'): exercises first/last (skip NA) and nunique (exclude NA) so the
    # exported code must match the null-skipping run-path on both engines.
    # Group 'a' ENDS in a null (so positional .last() diverges from drop_nulls),
    # group 'b' STARTS with a null (so positional .first() diverges).
    return pd.DataFrame({"g": ["a", "a", "a", "b", "b", "c", "c"], "v": [1.0, 3.0, None, None, 2.0, None, None]})


def _concat_a() -> pd.DataFrame:
    return pd.DataFrame({"x": [1, 2], "y": [10.0, 20.0]})


def _concat_b() -> pd.DataFrame:
    # Different column set from _concat_a ('z' instead of 'y'): concatRows must
    # union the columns and null-fill on both engines (diagonal concat).
    return pd.DataFrame({"x": [3, 4], "z": [30.0, 40.0]})


def _cast_multi() -> pd.DataFrame:
    return pd.DataFrame({"a": ["2024-01-02", None, "not a date"], "b": ["1.5", "x", "3"]})


# Case id -> input frames by handle. Ids whose result has no defined row order
# (grouping, pivoting) are listed in _SORT_BEFORE_COMPARE.
_CASE_INPUTS: dict[str, dict[str, Any]] = {
    "filter_eq": {"in": _num},
    "filter_isnull": {"in": _num},
    "filter_notnull": {"in": _num},
    "filter_between": {"in": _num},
    "filter_in_str": {"in": _text},
    "filter_in_list": {"in": _text},
    "filter_contains": {"in": _text},
    "filter_contains_dot": {"in": _text_special},
    "filter_contains_numeric": {"in": _text_special},
    "filter_startswith": {"in": _text},
    "filter_endswith": {"in": _text},
    "sort_default": {"in": _num},
    "sort_multi": {"in": _num},
    "limit_head": {"in": _num},
    "limit_offset": {"in": _num},
    "sample_frac": {"in": _num},
    "sample_n": {"in": _num},
    "dedupe_default": {"in": _num},
    "dedupe_subset": {"in": _num},
    "drop_cols": {"in": _num},
    "rename_cols": {"in": _single_col},
    "select_cols": {"in": _num},
    "cast_dt": {"in": _dates_str},
    "cast_dt_datetime": {"in": _datetimes},
    "cast_int_coerce": {"in": _ints_dirty},
    # numeric (not string) input: polars can't cast Utf8->Boolean at all, even
    # with strict=False, so this exercises the coerce path both engines support.
    "cast_bool_coerce": {"in": _num},
    "cast_plain": {"in": _num},
    "dropnull_any": {"in": _num},
    "dropnull_any_subset": {"in": _num},
    "dropnull_all": {"in": _num},
    "dropnull_all_subset": {"in": _num},
    "fill_const": {"in": _num},
    "fill_const_cols": {"in": _num},
    "fill_ffill": {"in": _num},
    "fill_ffill_cols": {"in": _num},
    "fill_mean": {"in": _num},
    "fill_mean_cols": {"in": _num},
    "fill_median": {"in": _num},
    "fill_median_all_null": {"in": _all_null_float},
    "fill_median_mixed": {"in": _mixed_dtypes},
    "fill_mean_mixed": {"in": _mixed_dtypes},
    "fill_mode_with_empty": {"in": _with_empty_col},
    "fill_const_text_mixed": {"in": _mixed_dtypes},
    "fill_const_num_mixed": {"in": _mixed_dtypes},
    "fill_mode": {"in": _num},
    "fill_mode_multimodal": {"in": _multimodal},
    "groupby": {"in": _num},
    "groupby_var": {"in": _num},
    "groupby_first": {"in": _group_null_vals},
    "groupby_last": {"in": _group_null_vals},
    "groupby_nunique": {"in": _group_null_vals},
    "concat": {"in": _num, "in_1": _num},
    "concat_mismatch": {"in": _concat_a, "in_1": _concat_b},
    "calc": {"in": _num},
    "dateparts": {"in": _dateparts_dt},
    "dateparts_str": {"in": _dateparts_str},
    "parse_dates": {"in": _dates_str},
    "parse_dates_fmt": {"in": _dates_str},
    "parse_dates_datetime": {"in": _datetimes},
    "date_diff": {"in": _date_pair_str},
    "date_diff_datetime": {"in": _date_pair_dt},
    "unpivot_min": {"in": _wide},
    "unpivot_full": {"in": _wide},
    "pivot_str_index": {"in": _pivotable},
    "pivot_count": {"in": _pivotable},
    "replace_literal": {"in": _text},
    "replace_regex": {"in": _text},
    "str_upper": {"in": _text},
    "str_lstrip": {"in": _text_with_surrounding_spaces},
    "str_rstrip": {"in": _text_with_surrounding_spaces},
    "str_replace": {"in": _text},
    "str_pad_right": {"in": _text},
    "str_pad_left": {"in": _text},
    "outlier_iqr_drop": {"in": _num},
    "outlier_z_clip": {"in": _num},
    "outlier_pct_drop": {"in": _num},
    "round": {"in": _num},
    "bin_equal": {"in": _num},
    "bin_quantile": {"in": _num},
    "join_on": {"left": _join_left, "right": _join_right},
    "join_split": {"left": _join_left, "right": _join_right},
    "join_outer": {"left": _join_left, "right": _join_right},
    "join_semi_on": {"left": _join_membership_left, "right": _join_membership_right},
    "join_anti_on": {"left": _join_membership_left, "right": _join_membership_right},
    "join_semi_incomplete_split": {
        "left": _join_incomplete_split_left,
        "right": _join_incomplete_split_right,
    },
    "join_anti_incomplete_split": {
        "left": _join_incomplete_split_left,
        "right": _join_incomplete_split_right,
    },
    "join_semi_split": {"left": _join_membership_left, "right": _join_membership_right},
    "join_anti_split": {"left": _join_membership_left, "right": _join_membership_right},
    "sort_desc": {"in": _num},
    "dedupe_keep_none": {"in": _num},
    "fill_bfill": {"in": _num},
    "fill_max_cols": {"in": _num},
    "cast_multi": {"in": _cast_multi},
    "parse_dates_two": {"in": _date_pair_str},
    "combine_cols": {"in": _mixed_dtypes},
    "combine_cols_drop": {"in": _mixed_dtypes},
    "combine_cols_spacey": {"in": _mixed_dtypes},
    "coalesce_cols": {"in": _mixed_dtypes},
    "conditional_rules": {"in": _num},
    "conditional_any": {"in": _num},
    "map_default": {"in": _text},
    "map_plain": {"in": _text},
    "split_delim": {"in": _text_special},
    "split_regex": {"in": _text},
    "explode_delim": {"in": _csvish},
    "filter_expr": {"in": _num},
    "window_row_number": {"in": _grouped},
    "window_rank": {"in": _grouped},
    "window_rank_desc_nopart": {"in": _grouped},
    "window_cumsum": {"in": _grouped},
    "window_cumprod": {"in": _grouped},
    "window_lag_nopart": {"in": _grouped},
    "window_rownum_order_nopart": {"in": _grouped},
    "window_rownum_null_order": {"in": _grouped},
    "window_rownum_multiorder": {"in": _grouped},
    "window_cumcount_noorder": {"in": _grouped},
    "rolling_part": {"in": _grouped},
    "rolling_nopart": {"in": _grouped},
    "rolling_plain": {"in": _grouped},
    "rowdiff_part": {"in": _grouped},
    "rowdiff_pct": {"in": _grouped},
    "outlier_iqr_multi": {"in": _num},
    "outlier_clip_multi": {"in": _num},
    "round_multi": {"in": _num},
}

_SORT_BEFORE_COMPARE = {
    "groupby",
    "groupby_var",
    "groupby_first",
    "groupby_last",
    "groupby_nunique",
    "pivot_str_index",
    "pivot_count",
}

_CASE_BY_ID = {case_id: (node_type, config) for case_id, node_type, config in CODEGEN_CASES}


def test_every_codegen_case_has_equivalence_data() -> None:
    missing = set(_CASE_BY_ID) - set(_CASE_INPUTS)
    assert not missing, f"add equivalence input data for new codegen case(s): {sorted(missing)}"


# --- comparison --------------------------------------------------------------


def _normalize(df: pd.DataFrame, sort: bool) -> pd.DataFrame:
    out = df.reset_index(drop=True)
    # pivot_table keeps the columns-index *name* ('c'); the engine strips it.
    # It's cosmetic metadata that no file output preserves — ignore it.
    out.columns.name = None
    if sort:
        out = out.sort_values(by=list(out.columns)).reset_index(drop=True)
    # Null spellings differ across engines/dtypes (None / NaN / NaT / pd.NA):
    # compare on a common object representation.
    out = out.astype(object).where(out.notna(), None)
    return out


def _assert_frames_match(expected: pd.DataFrame, got: pd.DataFrame, case_id: str) -> None:
    sort = case_id in _SORT_BEFORE_COMPARE
    assert list(expected.columns) == list(got.columns), (
        f"{case_id}: column mismatch\nexecute(): {list(expected.columns)}\ngenerated: {list(got.columns)}"
    )
    assert_frame_equal(
        _normalize(expected, sort),
        _normalize(got, sort),
        check_dtype=False,
        check_exact=False,
        rtol=1e-9,
        obj=f"{case_id} frame",
    )


def _vars_for(inputs: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    in_vars = {handle: f"in_{i}" for i, handle in enumerate(inputs)}
    return in_vars, {"out": "result"}


@pytest.mark.parametrize("case_id", sorted(_CASE_INPUTS), ids=sorted(_CASE_INPUTS))
def test_pandas_codegen_matches_execute(case_id: str) -> None:
    node_type, config = _CASE_BY_ID[case_id]
    t = get_transformation(node_type)
    frames = {h: build() for h, build in _CASE_INPUTS[case_id].items()}

    expected = t.execute(PandasEngine(), {h: f.copy() for h, f in frames.items()}, config)["out"]

    in_vars, out_vars = _vars_for(frames)
    code = t.to_python_code(in_vars, out_vars, config)
    ns: dict[str, Any] = {"pd": pd, **{in_vars[h]: f.copy() for h, f in frames.items()}}
    for imp in [*t.imports(config), *t.helpers(config)]:  # the header the driver would emit (e.g. numpy)
        exec(imp, ns)  # noqa: S102
    exec(compile(code, f"<pandas:{case_id}>", "exec"), ns)  # noqa: S102 - exercising generated code

    _assert_frames_match(expected, ns["result"], case_id)


@pytest.mark.parametrize("values", [["EU", None], [None, None], []], ids=["missing-part", "all-null", "empty"])
@pytest.mark.parametrize(
    "output_columns", [["region", "city"], ["region", "city", "country"]], ids=["two-outputs", "three-outputs"]
)
@pytest.mark.parametrize("mode", ["delimiter", "regex"])
@pytest.mark.parametrize("keep_original", [True, False], ids=["keep-source", "drop-source"])
@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_split_column_export_preserves_absent_parts(
    values: list[str | None], output_columns: list[str], mode: str, keep_original: bool, engine_name: str
) -> None:
    node = get_transformation("splitColumn")
    config = {
        "column": "location",
        "into": output_columns,
        "mode": mode,
        "delimiter": "|",
        "pattern": "(EU)",
        "keep_original": keep_original,
    }
    node.validate_config(config)
    source = pd.DataFrame({"location": pd.Series(values, dtype="string")})
    expected = pd.DataFrame({"region": values, **{name: [None] * len(values) for name in output_columns[1:]}})
    if keep_original:
        expected.insert(0, "location", values)

    if engine_name == "pandas":
        executed = node.execute(PandasEngine(), {"in": source}, config)["out"]
        code = node.to_python_code({"in": "source"}, {"out": "result"}, config)
        scope: dict[str, Any] = {"pd": pd, "source": source}
    else:
        frame = pl.from_pandas(source)
        executed = node.execute(PolarsEngine(), {"in": frame}, config)["out"].to_pandas()
        code = node.to_polars_code({"in": "source"}, {"out": "result"}, config)
        scope = {"pl": pl, "source": frame}

    _assert_frames_match(expected, executed, "split_absent_parts")
    exec(compile(code, "<split_absent_parts>", "exec"), scope)  # noqa: S102 - exercising exported code
    exported = scope["result"] if engine_name == "pandas" else scope["result"].to_pandas()
    _assert_frames_match(expected, exported, "split_absent_parts")


@pytest.mark.parametrize(
    ("aggfunc", "cells"),
    [("sum", [[1.0, 0.0], [3.0, None], [None, 4.0]]), ("count", [[1, 0], [1, None], [None, 1]])],
    ids=["sum", "count"],
)
@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_pivot_cell_without_rows_is_null_on_runtime_and_export(
    aggfunc: str, cells: list[list[float | None]], engine_name: str
) -> None:
    """A (row, column) pair with no source rows is null, never 0, on both engines
    and in both exports. A pair whose rows exist but hold only nulls still
    aggregates (r1/c2: sum 0, count 0), so the two cases stay distinguishable."""
    node = get_transformation("pivot")
    config = {"index": "r", "columns": "c", "values": "v", "aggfunc": aggfunc}
    source = pd.DataFrame({"r": ["r1", "r1", "r2", "r3"], "c": ["c1", "c2", "c1", "c2"], "v": [1.0, None, 3.0, 4.0]})
    expected = pd.DataFrame({"r": ["r1", "r2", "r3"], "c1": [row[0] for row in cells], "c2": [row[1] for row in cells]})

    if engine_name == "pandas":
        executed = node.execute(PandasEngine(), {"in": source}, config)["out"]
        code = node.to_python_code({"in": "source"}, {"out": "result"}, config)
        scope: dict[str, Any] = {"pd": pd, "source": source}
    else:
        frame = pl.from_pandas(source)
        executed = node.execute(PolarsEngine(), {"in": frame}, config)["out"].to_pandas()
        code = node.to_polars_code({"in": "source"}, {"out": "result"}, config)
        scope = {"pl": pl, "source": frame}

    _assert_frames_match(expected, executed, "pivot_str_index")
    exec(compile(code, "<pivot_cell_without_rows>", "exec"), scope)  # noqa: S102 - exercising exported code
    exported = scope["result"] if engine_name == "pandas" else scope["result"].to_pandas()
    _assert_frames_match(expected, exported, "pivot_str_index")


_BIN_LABELS = ["low", "mid", "high"]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        # The 1/3 and 2/3 quantiles are exactly 100 and 250: a value on an edge
        # belongs to the lower bin.
        ([15.0, 100.0, 250.0, 500.0], ["low", "low", "mid", "high"]),
        # The first edge equals the minimum: the tied minimum is its own bin.
        ([1.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0], ["low"] * 4 + ["mid"] + ["high"] * 3),
        # Both edges are 2, so the middle bin is empty; the top keeps its label.
        ([1.0, 2.0, 2.0, 2.0, 2.0, 2.0, 3.0], ["low"] * 6 + ["high"]),
        ([5.0, 5.0, 5.0, 5.0], ["low"] * 4),
        # Nulls stay null and do not shift the edges of the other values.
        ([1.0, None, 3.0, 4.0, 5.0, 6.0, None, 8.0], ["low", None, "low", "mid", "mid", "high", None, "high"]),
        ([None, None], [None, None]),
    ],
    ids=["value-on-edge", "tie-at-minimum", "tied-edges", "constant", "nulls", "all-null"],
)
@pytest.mark.parametrize("engine_name", ["pandas", "polars", "polars-lazy"])
def test_bin_quantile_edge_cases_agree_on_runtime_and_export(
    values: list[float | None], expected: list[str | None], engine_name: str
) -> None:
    """Quantile bins are (-inf, q1], (q1, q2], ..., (qk, inf] over the interior
    quantiles, on both engines and in every export. Default interval labels are
    formatted per engine, so they must partition the rows like the labels do."""
    node = get_transformation("binColumn")
    source = pd.DataFrame({"x": pd.Series(values, dtype="float64")})
    results = []
    for labels in (_BIN_LABELS, None):
        config = {"column": "x", "new_column": "tier", "method": "quantile", "bins": 3, "labels": labels}
        node.validate_config(config)
        if engine_name == "pandas":
            executed = node.execute(PandasEngine(), {"in": source.copy()}, config)["out"]
            code = node.to_python_code({"in": "source"}, {"out": "result"}, config)
            scope: dict[str, Any] = {"pd": pd, "source": source.copy()}
        else:
            frame = pl.from_pandas(source)
            executed = node.execute(PolarsEngine(), {"in": frame}, config)["out"].to_pandas()
            code = node.to_polars_code({"in": "source"}, {"out": "result"}, config)
            scope = {"pl": pl, "source": frame.lazy() if engine_name == "polars-lazy" else frame}
        exec(compile(code, "<bin_quantile_edges>", "exec"), scope)  # noqa: S102 - exercising exported code
        exported = scope["result"]
        if engine_name != "pandas":
            exported = (exported.collect() if engine_name == "polars-lazy" else exported).to_pandas()
        _assert_frames_match(executed, exported, "bin_quantile_edges")
        results.append([None if pd.isna(v) else v for v in executed["tier"]])

    labelled, default = results
    assert labelled == expected
    pairs = {(a, b) for a, b in zip(labelled, default, strict=True)}
    assert all((a is None) == (b is None) for a, b in pairs)
    assert len({a for a, _ in pairs}) == len({b for _, b in pairs}) == len(pairs)


def test_polars_fill_mode_all_null_column_is_left_untouched() -> None:
    """Regression: mode() with nulls present can make null itself the mode, and
    fill_null(None) raises. The emitter must drop nulls first and, like the
    engine, leave an all-null column as-is instead of crashing."""
    t = get_transformation("fillNulls")
    config = {"strategy": "mode"}  # no columns -> every column, incl. all-null
    frame = pd.DataFrame({"a": [1.0, 1.0, None], "empty": [None, None, None]})

    expected = t.execute(PolarsEngine(), {"in": pl.from_pandas(frame)}, config)["out"]

    code = t.to_polars_code({"in": "in_0"}, {"out": "result"}, config)
    ns: dict[str, Any] = {"pl": pl, "in_0": pl.from_pandas(frame)}
    exec(compile(code, "<polars:fill_mode_all_null>", "exec"), ns)  # noqa: S102

    _assert_frames_match(expected.to_pandas(), ns["result"].to_pandas(), "fill_mode_all_null")
    assert ns["result"]["a"].null_count() == 0
    assert ns["result"]["empty"].null_count() == 3


# Integer ids, an integer 'age' with one null and an outlier, and a text
# 'region' with one null — read from CSV the way each exported script reads it
# (pandas: float64 age, polars: Int64 age).
_SURVEY_CSV = "respondent_id,age,region\n1,25,North\n2,,South\n3,40,\n4,31,East\n5,95,North\n"
_SURVEY_AGE = [25, None, 40, 31, 95]
_SURVEY_REGION = ["North", "South", None, "East", "North"]


@pytest.mark.parametrize(
    ("config", "age", "region"),
    [
        # mean of 25, 40, 31, 95 is 47.75, not the integer 47
        ({"strategy": "mean", "columns": ["age"]}, 47.75, None),
        ({"strategy": "mean"}, 47.75, None),
        # median of an even count is the midpoint 35.5
        ({"strategy": "median", "columns": ["age"]}, 35.5, None),
        ({"strategy": "median"}, 35.5, None),
        # a selected null-free integer column (the id) is left as is
        ({"strategy": "mean", "columns": ["respondent_id", "age"]}, 47.75, None),
        ({"strategy": "median", "columns": ["respondent_id", "age"]}, 35.5, None),
        # all columns: a text constant skips the numeric column ...
        ({"strategy": "constant", "value": "Unknown"}, None, "Unknown"),
        # ... and a number-like constant (the editor sends text) fills both
        ({"strategy": "constant", "value": "0"}, 0, "0"),
    ],
    ids=[
        "mean-cols",
        "mean-all",
        "median-cols",
        "median-all",
        "mean-cols-with-id",
        "median-cols-with-id",
        "const-text-all",
        "const-number-all",
    ],
)
def test_fill_nulls_every_path_fills_the_same_values(config: dict[str, Any], age: Any, region: Any) -> None:
    """Both engines, both exports and the lazy Polars export fill identically."""
    t = get_transformation("fillNulls")
    expected = pd.DataFrame(
        {
            "respondent_id": [1, 2, 3, 4, 5],
            "age": [age if v is None else v for v in _SURVEY_AGE],
            "region": [region if v is None else v for v in _SURVEY_REGION],
        }
    )

    def pandas_frame() -> pd.DataFrame:
        return pd.read_csv(io.StringIO(_SURVEY_CSV))

    def polars_frame() -> pl.DataFrame:
        return pl.read_csv(io.StringIO(_SURVEY_CSV))

    pandas_ns: dict[str, Any] = {"pd": pd, "src": pandas_frame()}
    exec(compile(t.to_python_code({"in": "src"}, {"out": "result"}, config), "<pandas>", "exec"), pandas_ns)  # noqa: S102
    polars_code = compile(t.to_polars_code({"in": "src"}, {"out": "result"}, config), "<polars>", "exec")
    polars_ns: dict[str, Any] = {"pl": pl, "src": polars_frame()}
    exec(polars_code, polars_ns)  # noqa: S102 - exercising exported code
    lazy_ns: dict[str, Any] = {"pl": pl, "src": polars_frame().lazy()}
    exec(polars_code, lazy_ns)  # noqa: S102 - exercising exported code

    results = {
        "pandas run": t.execute(PandasEngine(), {"in": pandas_frame()}, config)["out"],
        "pandas export": pandas_ns["result"],
        "polars run": t.execute(PolarsEngine(), {"in": polars_frame()}, config)["out"].to_pandas(),
        "polars export": polars_ns["result"].to_pandas(),
        "polars lazy export": lazy_ns["result"].collect().to_pandas(),
    }
    for path, got in results.items():
        _assert_frames_match(expected, got, f"{config} via {path}")
        # The null-free id column keeps its integer type (no 1.0 in a CSV).
        assert pd.api.types.is_integer_dtype(got["respondent_id"]), f"{config} via {path}"


@pytest.mark.parametrize("case_id", sorted(_CASE_INPUTS), ids=sorted(_CASE_INPUTS))
def test_polars_codegen_matches_execute(case_id: str) -> None:
    node_type, config = _CASE_BY_ID[case_id]
    t = get_transformation(node_type)
    frames = {h: pl.from_pandas(build()) for h, build in _CASE_INPUTS[case_id].items()}

    expected = t.execute(PolarsEngine(), dict(frames), config)["out"]

    in_vars, out_vars = _vars_for(frames)
    code = t.to_polars_code(in_vars, out_vars, config)
    ns: dict[str, Any] = {"pl": pl, **{in_vars[h]: f for h, f in frames.items()}}
    for imp in [*t.polars_imports(config), *t.polars_helpers(config)]:  # the header the polars driver would emit
        exec(imp, ns)  # noqa: S102
    exec(compile(code, f"<polars:{case_id}>", "exec"), ns)  # noqa: S102 - exercising generated code

    _assert_frames_match(expected.to_pandas(), ns["result"].to_pandas(), case_id)


# --- filterRows: values arrive as text --------------------------------------
# The editor saves a Filter Rows value as text, so a numeric comparison is
# "amount > '100'". Every runtime and export path must compare it in the
# column's type: numbers for a numeric column, text (leading zeros kept) for a
# text column, and an error for text that is not a number.

_FILTER_CSV = "row,amount,qty,zip\n1,50.0,5,02134\n2,150.0,15,2134\n3,1000.5,150,x\n4,99.5,20,02134x\n"

_FILTER_TEXT_VALUE_CASES = [
    ("amount", "==", {"value": "150"}, [2]),
    ("amount", "!=", {"value": "150"}, [1, 3, 4]),
    ("amount", ">", {"value": "100"}, [2, 3]),
    ("amount", ">=", {"value": "150"}, [2, 3]),
    ("amount", "<", {"value": "100"}, [1, 4]),
    ("amount", "<=", {"value": "99.5"}, [1, 4]),
    ("amount", "between", {"value": "50", "value2": "150"}, [1, 2, 4]),
    ("amount", "in", {"value": "50, 150"}, [1, 2]),
    # Mixed int/float items in either order: polars builds the list's dtype from
    # its first item, so every item must be a float once one is.
    ("amount", "in", {"value": "50, 99.5"}, [1, 4]),
    ("amount", "in", {"value": "99.5, 50"}, [1, 4]),
    ("amount", "between", {"value": "50", "value2": "99.5"}, [1, 4]),
    ("amount", "between", {"value": "99.5", "value2": "1000"}, [2, 4]),
    ("qty", "==", {"value": "15"}, [2]),
    ("qty", ">", {"value": "19.5"}, [3, 4]),
    ("qty", "in", {"value": "5, 20"}, [1, 4]),
    ("qty", "in", {"value": "5, 19.5"}, [1]),
    ("qty", "in", {"value": "19.5, 20"}, [4]),
    ("qty", "between", {"value": "5", "value2": "15.5"}, [1, 2]),
    ("zip", "==", {"value": "02134"}, [1]),
    ("zip", "in", {"value": "02134, x"}, [1, 3]),
    ("zip", "between", {"value": "02134", "value2": "2134"}, [1, 2, 4]),
]

_FILTER_RUNNERS = ["pandas", "polars", "pandas-script", "polars-script", "polars-lazy-script"]


def _filter_graph(config: dict[str, Any], out_path: str, node_type: str) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d"}}},
            {"id": "flt", "type": node_type, "data": {"config": config}},
            {"id": "out", "type": "csvOutput", "data": {"config": {"path": out_path}}},
        ],
        "edges": [
            {"id": "e1", "source": "in", "target": "flt"},
            {"id": "e2", "source": "flt", "target": "out"},
        ],
    }


def _run_filter(
    runner: str,
    config: dict[str, Any],
    tmp_path: Any,
    node_type: str = "filterRows",
    parameters: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Run csv -> node -> csv through the app engine or an exported script. Flow
    ``parameters`` resolve the way a run and an export resolve them."""
    from app.engine.codegen import CodeGenerator
    from app.engine.codegen_params import parameter_block_lines, substitute_for_codegen
    from app.engine.executor import FlowExecutor, dataset_ref_key
    from app.engine.parameters import apply_parameters
    from app.engine.polars_codegen import PolarsCodeGenerator

    source = tmp_path / "in.csv"
    source.write_text(_FILTER_CSV, encoding="utf-8")
    out = tmp_path / "out.csv"
    graph = _filter_graph(config, str(out), node_type)
    if parameters:
        graph["parameters"] = parameters
    if runner in ("pandas", "polars"):
        resolved, _ = apply_parameters(graph, {})
        outputs = FlowExecutor().execute(resolved, {dataset_ref_key("d", None): source}, tmp_path, engine_name=runner)
        return pd.read_csv(next(iter(outputs.values())), dtype={"zip": str})
    code_graph, param_lines = substitute_for_codegen(graph), parameter_block_lines(graph)
    if runner == "pandas-script":
        code = CodeGenerator().generate(code_graph, {"d": str(source)}, parameter_lines=param_lines)
    else:
        lazy = runner == "polars-lazy-script"
        code = PolarsCodeGenerator().generate(code_graph, {"d": str(source)}, lazy=lazy, parameter_lines=param_lines)
    exec(compile(code, f"<{runner}>", "exec"), {})  # noqa: S102 - exercising the exported script
    return pd.read_csv(out, dtype={"zip": str})


@pytest.mark.parametrize("runner", _FILTER_RUNNERS)
@pytest.mark.parametrize(
    ("column", "operator", "values", "kept"),
    _FILTER_TEXT_VALUE_CASES,
    ids=[f"{c}{op}{v['value']}" for c, op, v, _ in _FILTER_TEXT_VALUE_CASES],
)
def test_filter_rows_text_value_compares_in_column_type(
    column: str, operator: str, values: dict[str, Any], kept: list[int], runner: str, tmp_path: Any
) -> None:
    result = _run_filter(runner, {"column": column, "operator": operator, **values}, tmp_path)
    assert sorted(result["row"]) == kept
    if column == "zip":
        assert "02134" in set(result["zip"])  # compared as text: the leading zero survives


# An `in` value may be a flow parameter: the run splits the resolved value on
# commas, and the export must split the parameter variable the same way.
_IN_PARAMETER_CASES = [
    ("qty", "{{ ids }}", {"name": "ids", "type": "string", "default": "5, 20"}, [1, 4]),
    ("zip", "{{ ids }}", {"name": "ids", "type": "string", "default": "02134, x"}, [1, 3]),
    ("qty", "{{ ids }}", {"name": "ids", "type": "integer", "default": 15}, [2]),
    ("qty", "5, {{ ids }}", {"name": "ids", "type": "integer", "default": 20}, [1, 4]),
]


@pytest.mark.parametrize("runner", _FILTER_RUNNERS)
@pytest.mark.parametrize(
    ("column", "value", "parameter", "kept"),
    _IN_PARAMETER_CASES,
    ids=["text-list", "text-list-on-text", "integer", "embedded"],
)
def test_filter_rows_in_resolves_a_parameter_like_the_run(
    column: str, value: str, parameter: dict[str, Any], kept: list[int], runner: str, tmp_path: Any
) -> None:
    config = {"column": column, "operator": "in", "value": value}
    result = _run_filter(runner, config, tmp_path, parameters=[parameter])
    assert sorted(result["row"]) == kept


# Text that is not a number fails in the app on both engines. An export keeps
# such text a plain literal (only number-like text is typed at runtime), so the
# scripts are checked only where a number-like item puts the helper in play.
_NOT_A_NUMBER_CASES = [
    ("gt", {"column": "amount", "operator": ">", "value": "abc"}, ["pandas", "polars"]),
    ("eq", {"column": "amount", "operator": "==", "value": "abc"}, ["pandas", "polars"]),
    ("between", {"column": "amount", "operator": "between", "value": "1", "value2": "lots"}, _FILTER_RUNNERS),
    ("in", {"column": "qty", "operator": "in", "value": "5, x"}, _FILTER_RUNNERS),
]


@pytest.mark.parametrize(
    ("config", "runner"),
    [(config, runner) for _, config, runners in _NOT_A_NUMBER_CASES for runner in runners],
    ids=[f"{case_id}-{runner}" for case_id, _, runners in _NOT_A_NUMBER_CASES for runner in runners],
)
def test_filter_rows_rejects_text_that_is_not_a_number(config: dict[str, Any], runner: str, tmp_path: Any) -> None:
    with pytest.raises(Exception, match=r"is not a number, but column '(amount|qty)' is numeric"):
        _run_filter(runner, config, tmp_path)


# conditionalColumn conditions come from the same kind of text input, so a
# condition value is typed against its column exactly like a Filter Rows value.
_CONDITION_TEXT_VALUE_CASES = [
    ("amount", ">=", "150", [2, 3]),
    ("amount", "<", "99.75", [1, 4]),
    ("qty", "==", "15", [2]),
    ("zip", "==", "02134", [1]),
]


def _conditional_config(column: str, operator: str, value: str) -> dict[str, Any]:
    return {
        "new_column": "tier",
        "default": "other",
        "rules": [{"conditions": [{"column": column, "operator": operator, "value": value}], "result": "hit"}],
    }


@pytest.mark.parametrize("runner", _FILTER_RUNNERS)
@pytest.mark.parametrize(
    ("column", "operator", "value", "hits"),
    _CONDITION_TEXT_VALUE_CASES,
    ids=[f"{c}{op}{v}" for c, op, v, _ in _CONDITION_TEXT_VALUE_CASES],
)
def test_conditional_column_text_value_compares_in_column_type(
    column: str, operator: str, value: str, hits: list[int], runner: str, tmp_path: Any
) -> None:
    result = _run_filter(runner, _conditional_config(column, operator, value), tmp_path, "conditionalColumn")
    assert sorted(result.loc[result["tier"] == "hit", "row"]) == hits


@pytest.mark.parametrize("runner", ["pandas", "polars"])
def test_conditional_column_rejects_text_that_is_not_a_number(runner: str, tmp_path: Any) -> None:
    with pytest.raises(Exception, match=r"is not a number, but column 'amount' is numeric"):
        _run_filter(runner, _conditional_config("amount", ">", "abc"), tmp_path, "conditionalColumn")
