"""Phase 2/3 node behavior: new options on existing nodes and the new node
types, exercised through the transformation layer on **both** engines, plus
codegen-compile checks for both generators."""

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.registry import get_transformation


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def run(engine, node_type, pdf, config, inputs=None):
    t = get_transformation(node_type)
    t.validate_config(config)
    ins = (
        {"in": _native(engine, pdf)}
        if inputs is None
        else {k: _native(engine, v) for k, v in inputs.items()}
    )
    return engine.to_pandas(t.execute(engine, ins, config)["out"])


# -- Phase 2: enriched existing nodes ------------------------------------


def test_drop_nulls_how_all(engine):
    pdf = pd.DataFrame({"a": [1.0, None, None], "b": [1.0, 2.0, None]})
    out = run(engine, "dropNulls", pdf, {"how": "all", "subset": ["a", "b"]})
    assert len(out) == 2  # only the fully-null row is dropped


def test_cast_coerce_numeric(engine):
    pdf = pd.DataFrame({"x": ["1", "2", "bad"]})
    out = run(engine, "castDtypes", pdf, {"casts": {"x": "integer"}, "errors": "coerce"})
    assert out["x"].tolist()[:2] == [1, 2]
    assert pd.isna(out["x"].tolist()[2])


def test_cast_datetime_with_format(engine):
    pdf = pd.DataFrame({"d": ["01-2021", "02-2021"]})
    out = run(engine, "castDtypes", pdf, {"casts": {"d": "datetime"}, "format": "%m-%Y"})
    assert pd.api.types.is_datetime64_any_dtype(out["d"])


def test_limit_rows_offset(engine):
    pdf = pd.DataFrame({"a": [0, 1, 2, 3, 4]})
    out = run(engine, "limitRows", pdf, {"n": 2, "offset": 1})
    assert out["a"].tolist() == [1, 2]


def test_replace_values_regex(engine):
    pdf = pd.DataFrame({"s": ["a1", "b2"]})
    out = run(
        engine,
        "replaceValues",
        pdf,
        {"column": "s", "to_replace": r"\d", "value": "X", "regex": True},
    )
    assert out["s"].tolist() == ["aX", "bX"]


def test_string_replace(engine):
    pdf = pd.DataFrame({"s": ["abc", "aaa"]})
    out = run(
        engine,
        "stringTransform",
        pdf,
        {"column": "s", "operation": "replace", "find": "a", "replace_with": "Z"},
    )
    assert out["s"].tolist() == ["Zbc", "ZZZ"]


def test_string_len(engine):
    pdf = pd.DataFrame({"s": ["ab", "abc"]})
    out = run(engine, "stringTransform", pdf, {"column": "s", "operation": "len"})
    assert out["s"].tolist() == [2, 3]


def test_string_pad(engine):
    pdf = pd.DataFrame({"s": ["7"]})
    out = run(
        engine,
        "stringTransform",
        pdf,
        {"column": "s", "operation": "pad", "width": 5, "fill_char": "0"},
    )
    assert out["s"].tolist() == ["00007"]


def test_sort_na_position_first(engine):
    pdf = pd.DataFrame({"x": [2.0, None, 1.0]})
    out = run(
        engine,
        "sortRows",
        pdf,
        {"columns": ["x"], "ascending": True, "na_position": "first"},
    )
    assert pd.isna(out["x"].tolist()[0])


def test_groupby_std(engine):
    pdf = pd.DataFrame({"g": ["a", "a", "b"], "v": [1.0, 3.0, 5.0]})
    out = run(engine, "groupByAggregate", pdf, {"group_by": ["g"], "aggregations": {"v": "std"}})
    assert set(out.columns) == {"g", "v"}


def test_join_left_right_on(engine):
    left = pd.DataFrame({"lid": [1, 2], "x": ["a", "b"]})
    right = pd.DataFrame({"rid": [1, 2], "y": ["c", "d"]})
    out = run(
        engine,
        "join",
        None,
        {"left_on": ["lid"], "right_on": ["rid"], "how": "inner"},
        inputs={"left": left, "right": right},
    )
    assert len(out) == 2
    assert "y" in out.columns


# -- Phase 3: new nodes --------------------------------------------------


def test_sample_rows_n(engine):
    pdf = pd.DataFrame({"a": range(10)})
    out = run(engine, "sampleRows", pdf, {"n": 3, "seed": 1})
    assert len(out) == 3


def test_sample_rows_frac(engine):
    pdf = pd.DataFrame({"a": range(10)})
    out = run(engine, "sampleRows", pdf, {"frac": 0.5, "seed": 1})
    assert len(out) == 5


def test_remove_outliers_iqr_drop(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 100.0]})
    out = run(engine, "removeOutliers", pdf, {"columns": ["v"], "method": "iqr", "action": "drop"})
    assert 100.0 not in out["v"].tolist()
    assert len(out) == 3


def test_remove_outliers_zscore_clip(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 100.0]})
    out = run(
        engine,
        "removeOutliers",
        pdf,
        {"columns": ["v"], "method": "zscore", "action": "clip", "threshold": 1},
    )
    assert max(out["v"].tolist()) < 100.0


def test_remove_outliers_percentile_drop(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 100.0]})
    out = run(
        engine,
        "removeOutliers",
        pdf,
        {"columns": ["v"], "method": "percentile", "action": "drop", "lower": 0, "upper": 75},
    )
    assert 100.0 not in out["v"].tolist()


def test_round_numbers(engine):
    pdf = pd.DataFrame({"x": [1.234, 5.678]})
    out = run(engine, "roundNumbers", pdf, {"columns": ["x"], "decimals": 1})
    assert out["x"].tolist() == [1.2, 5.7]


def test_bin_column_equalwidth(engine):
    pdf = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = run(
        engine,
        "binColumn",
        pdf,
        {"column": "x", "new_column": "bucket", "method": "equalwidth", "bins": 2},
    )
    assert "bucket" in out.columns
    assert out["bucket"].nunique() == 2


def test_bin_column_quantile(engine):
    pdf = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = run(
        engine,
        "binColumn",
        pdf,
        {"column": "x", "new_column": "q", "method": "quantile", "bins": 2},
    )
    assert "q" in out.columns


def test_extract_date_parts(engine):
    pdf = pd.DataFrame({"d": ["2021-01-02", "2021-06-15"]})
    out = run(engine, "extractDateParts", pdf, {"column": "d", "parts": ["year", "month"]})
    assert out["d_year"].tolist() == [2021, 2021]
    assert "d_month" in out.columns


def test_unpivot(engine):
    pdf = pd.DataFrame({"id": [1], "a": [10], "b": [20]})
    out = run(engine, "unpivot", pdf, {"id_vars": ["id"], "var_name": "k", "value_name": "v"})
    assert len(out) == 2
    assert set(out["k"]) == {"a", "b"}


def test_pivot(engine):
    pdf = pd.DataFrame({"r": ["x", "x", "y"], "c": ["m", "n", "m"], "v": [1, 2, 3]})
    out = run(
        engine,
        "pivot",
        pdf,
        {"index": ["r"], "columns": "c", "values": "v", "aggfunc": "sum"},
    )
    assert "m" in out.columns


# -- generated code is valid Python for both engines ---------------------

_CODEGEN_CASES = [
    ("dropNulls", {"how": "all", "subset": ["a"]}, {"in": "df_1"}),
    ("castDtypes", {"casts": {"a": "integer"}, "errors": "coerce"}, {"in": "df_1"}),
    ("castDtypes", {"casts": {"a": "datetime"}, "format": "%Y"}, {"in": "df_1"}),
    ("limitRows", {"n": 5, "offset": 2}, {"in": "df_1"}),
    (
        "replaceValues",
        {"column": "a", "to_replace": r"\d", "value": "X", "regex": True},
        {"in": "df_1"},
    ),
    (
        "stringTransform",
        {"column": "a", "operation": "replace", "find": "x", "replace_with": "y"},
        {"in": "df_1"},
    ),
    (
        "stringTransform",
        {"column": "a", "operation": "pad", "width": 4, "side": "right"},
        {"in": "df_1"},
    ),
    ("stringTransform", {"column": "a", "operation": "len"}, {"in": "df_1"}),
    ("sortRows", {"columns": ["a"], "na_position": "first"}, {"in": "df_1"}),
    (
        "join",
        {"left_on": ["a"], "right_on": ["b"], "how": "left"},
        {"left": "df_1", "right": "df_0"},
    ),
    ("join", {"on": ["a"], "how": "inner"}, {"left": "df_1", "right": "df_0"}),
    ("sampleRows", {"n": 3, "seed": 1}, {"in": "df_1"}),
    ("sampleRows", {"frac": 0.5}, {"in": "df_1"}),
    ("removeOutliers", {"columns": ["a"], "method": "iqr", "action": "drop"}, {"in": "df_1"}),
    ("removeOutliers", {"columns": ["a"], "method": "zscore", "action": "clip"}, {"in": "df_1"}),
    (
        "removeOutliers",
        {"columns": ["a"], "method": "percentile", "action": "clip"},
        {"in": "df_1"},
    ),
    ("roundNumbers", {"columns": ["a"], "decimals": 2}, {"in": "df_1"}),
    (
        "binColumn",
        {"column": "a", "new_column": "b", "method": "equalwidth", "bins": 3},
        {"in": "df_1"},
    ),
    (
        "binColumn",
        {"column": "a", "new_column": "b", "method": "quantile", "bins": 3},
        {"in": "df_1"},
    ),
    ("extractDateParts", {"column": "d", "parts": ["year", "month"]}, {"in": "df_1"}),
    ("unpivot", {"id_vars": ["id"], "var_name": "k", "value_name": "v"}, {"in": "df_1"}),
    (
        "pivot",
        {"index": ["r"], "columns": "c", "values": "v", "aggfunc": "sum"},
        {"in": "df_1"},
    ),
]


@pytest.mark.parametrize("node_type,config,input_vars", _CODEGEN_CASES)
def test_codegen_compiles_for_both_engines(node_type, config, input_vars):
    t = get_transformation(node_type)
    out_vars = {"out": "df_2"}
    compile(t.to_python_code(input_vars, out_vars, config), "<pandas>", "exec")
    compile(t.to_polars_code(input_vars, out_vars, config), "<polars>", "exec")


# -- validation rejects bad configs --------------------------------------


@pytest.mark.parametrize(
    "node_type,config",
    [
        ("dropNulls", {"how": "bogus"}),
        ("sampleRows", {}),
        ("removeOutliers", {"columns": []}),
        ("removeOutliers", {"columns": ["v"], "method": "bogus"}),
        ("roundNumbers", {"columns": []}),
        ("binColumn", {"column": "x", "new_column": "b", "bins": 1}),
        ("extractDateParts", {"column": "d", "parts": ["nope"]}),
        ("unpivot", {}),
        ("pivot", {"index": ["r"], "columns": "c"}),
        ("stringTransform", {"column": "s", "operation": "pad"}),
        ("join", {}),
    ],
)
def test_validate_rejects_bad_config(node_type, config):
    with pytest.raises(ValueError):
        get_transformation(node_type).validate_config(config)
