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


def _dates_str() -> pd.DataFrame:
    return pd.DataFrame({"a": ["2024-01-02", "2024-03-04", None]})


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


def _text_special() -> pd.DataFrame:
    # "z.b" vs "zxb" separates regex from literal contains; "x5"/"5 stars"
    # exercise a numeric search value against stringified cells.
    return pd.DataFrame({"a": ["z.b", "zxb", "x5", None, "5 stars"]})


def _wide() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2], "x": [3.0, 4.0], "y": [5.0, 6.0]})


def _pivotable() -> pd.DataFrame:
    return pd.DataFrame({"r": ["r1", "r1", "r2"], "c": ["c1", "c2", "c1"], "v": [1.0, 2.0, 3.0]})


def _join_left() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2, 3], "lid": [1, 2, 3], "v": [10.0, 20.0, 30.0]})


def _join_right() -> pd.DataFrame:
    return pd.DataFrame({"id": [2, 3, 4], "rid": [2, 3, 4], "v": [7.0, 8.0, 9.0]})


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
    "fill_mode": {"in": _num},
    "groupby": {"in": _num},
    "concat": {"in": _num, "in_1": _num},
    "calc": {"in": _num},
    "dateparts": {"in": _datetimes},
    "dateparts_str": {"in": _dates_str},
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
}

_SORT_BEFORE_COMPARE = {"groupby", "pivot_str_index", "pivot_count"}

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
    exec(compile(code, f"<pandas:{case_id}>", "exec"), ns)  # noqa: S102 - exercising generated code

    _assert_frames_match(expected, ns["result"], case_id)


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


@pytest.mark.parametrize("case_id", sorted(_CASE_INPUTS), ids=sorted(_CASE_INPUTS))
def test_polars_codegen_matches_execute(case_id: str) -> None:
    node_type, config = _CASE_BY_ID[case_id]
    t = get_transformation(node_type)
    frames = {h: pl.from_pandas(build()) for h, build in _CASE_INPUTS[case_id].items()}

    expected = t.execute(PolarsEngine(), dict(frames), config)["out"]

    in_vars, out_vars = _vars_for(frames)
    code = t.to_polars_code(in_vars, out_vars, config)
    ns: dict[str, Any] = {"pl": pl, **{in_vars[h]: f for h, f in frames.items()}}
    exec(compile(code, f"<polars:{case_id}>", "exec"), ns)  # noqa: S102 - exercising generated code

    _assert_frames_match(expected.to_pandas(), ns["result"].to_pandas(), case_id)
