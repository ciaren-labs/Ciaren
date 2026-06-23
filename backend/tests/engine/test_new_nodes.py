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


def test_split_column_delimiter(engine):
    pdf = pd.DataFrame({"name": ["Ada Lovelace", "Alan Turing"]})
    out = run(
        engine,
        "splitColumn",
        pdf,
        {"column": "name", "mode": "delimiter", "delimiter": " ", "into": ["first", "last"]},
    )
    assert out["first"].tolist() == ["Ada", "Alan"]
    assert out["last"].tolist() == ["Lovelace", "Turing"]
    assert "name" in out.columns  # keep_original defaults to True


def test_split_column_regex_and_drop_original(engine):
    pdf = pd.DataFrame({"code": ["A-100", "B-200"]})
    out = run(
        engine,
        "splitColumn",
        pdf,
        {
            "column": "code",
            "mode": "regex",
            "pattern": r"([A-Z])-(\d+)",
            "into": ["letter", "number"],
            "keep_original": False,
        },
    )
    assert out["letter"].tolist() == ["A", "B"]
    assert out["number"].tolist() == ["100", "200"]
    assert "code" not in out.columns


def test_parse_dates_coerce(engine):
    pdf = pd.DataFrame({"d": ["2021-01-02", "not-a-date"]})
    out = run(engine, "parseDates", pdf, {"columns": ["d"], "errors": "coerce"})
    assert pd.api.types.is_datetime64_any_dtype(out["d"])
    assert pd.isna(out["d"].tolist()[1])


def test_parse_dates_with_format(engine):
    pdf = pd.DataFrame({"d": ["02-01-2021", "15-06-2021"]})
    out = run(engine, "parseDates", pdf, {"columns": ["d"], "format": "%d-%m-%Y"})
    assert out["d"].dt.year.tolist() == [2021, 2021]
    assert out["d"].dt.month.tolist() == [1, 6]


def test_map_values_keeps_unmapped(engine):
    pdf = pd.DataFrame({"grade": ["A", "B", "C"]})
    out = run(
        engine,
        "mapValues",
        pdf,
        {"column": "grade", "new_column": "label", "mapping": {"A": "Pass", "B": "Pass"}},
    )
    assert out["label"].tolist() == ["Pass", "Pass", "C"]


def test_map_values_with_default(engine):
    pdf = pd.DataFrame({"grade": ["A", "B", "C"]})
    out = run(
        engine,
        "mapValues",
        pdf,
        {
            "column": "grade",
            "mapping": {"A": "Pass", "B": "Pass"},
            "default": "Fail",
            "use_default": True,
        },
    )
    assert out["grade"].tolist() == ["Pass", "Pass", "Fail"]


def test_window_row_number_partitioned(engine):
    pdf = pd.DataFrame(
        {"region": ["E", "E", "W", "E"], "amount": [10, 30, 5, 20]}
    )
    out = run(
        engine,
        "windowFunction",
        pdf,
        {
            "function": "row_number",
            "partition_by": ["region"],
            "order_by": ["amount"],
            "new_column": "rn",
        },
    )
    # Row order is preserved; rn is the per-region rank by ascending amount.
    assert out["region"].tolist() == ["E", "E", "W", "E"]
    assert out["rn"].tolist() == [1, 3, 1, 2]


def test_window_running_total(engine):
    pdf = pd.DataFrame({"g": ["a", "a", "a"], "o": [1, 2, 3], "v": [10, 20, 30]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {
            "function": "cumsum",
            "partition_by": ["g"],
            "order_by": ["o"],
            "target": "v",
            "new_column": "running",
        },
    )
    assert out["running"].tolist() == [10, 30, 60]


def test_window_rank_descending(engine):
    pdf = pd.DataFrame({"score": [50, 90, 70]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {"function": "rank", "order_by": ["score"], "descending": True, "new_column": "r"},
    )
    assert out["r"].tolist() == [3, 1, 2]


def test_window_lag(engine):
    pdf = pd.DataFrame({"o": [1, 2, 3], "v": [10, 20, 30]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {"function": "lag", "order_by": ["o"], "target": "v", "offset": 1, "new_column": "prev"},
    )
    assert out["prev"].tolist()[0] is None or pd.isna(out["prev"].tolist()[0])
    assert out["prev"].tolist()[1:] == [10, 20]


def test_conditional_column_priority(engine):
    pdf = pd.DataFrame({"score": [95, 75, 40]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "grade",
            "default": "F",
            "rules": [
                {"column": "score", "operator": ">=", "value": 90, "result": "A"},
                {"column": "score", "operator": ">=", "value": 70, "result": "B"},
            ],
        },
    )
    assert out["grade"].tolist() == ["A", "B", "F"]


def test_conditional_column_string_operator(engine):
    pdf = pd.DataFrame({"email": ["a@gmail.com", "b@work.org"]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "kind",
            "default": "other",
            "rules": [
                {
                    "column": "email",
                    "operator": "endswith",
                    "value": "gmail.com",
                    "result": "personal",
                },
            ],
        },
    )
    assert out["kind"].tolist() == ["personal", "other"]


def test_conditional_column_match_all_and(engine):
    pdf = pd.DataFrame({"age": [30, 30, 15], "country": ["US", "CA", "US"]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "segment",
            "default": "other",
            "rules": [
                {
                    "match": "all",
                    "conditions": [
                        {"column": "age", "operator": ">=", "value": 18},
                        {"column": "country", "operator": "==", "value": "US"},
                    ],
                    "result": "us_adult",
                },
            ],
        },
    )
    # Only the first row satisfies BOTH conditions.
    assert out["segment"].tolist() == ["us_adult", "other", "other"]


def test_conditional_column_match_any_or(engine):
    pdf = pd.DataFrame({"plan": ["vip", "free", "free"], "spend": [0, 500, 10]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "priority",
            "default": "low",
            "rules": [
                {
                    "match": "any",
                    "conditions": [
                        {"column": "plan", "operator": "==", "value": "vip"},
                        {"column": "spend", "operator": ">=", "value": 100},
                    ],
                    "result": "high",
                },
            ],
        },
    )
    # Either being a VIP or spending >= 100 is enough.
    assert out["priority"].tolist() == ["high", "high", "low"]


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
    (
        "splitColumn",
        {"column": "a", "mode": "delimiter", "delimiter": "-", "into": ["x", "y"]},
        {"in": "df_1"},
    ),
    (
        "splitColumn",
        {
            "column": "a",
            "mode": "regex",
            "pattern": r"(\d+)",
            "into": ["x"],
            "keep_original": False,
        },
        {"in": "df_1"},
    ),
    ("parseDates", {"columns": ["d"], "format": "%Y-%m-%d", "errors": "coerce"}, {"in": "df_1"}),
    ("mapValues", {"column": "a", "mapping": {"x": "y"}}, {"in": "df_1"}),
    (
        "windowFunction",
        {"function": "row_number", "partition_by": ["g"], "order_by": ["o"], "new_column": "rn"},
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {"function": "rank", "order_by": ["o"], "descending": True, "new_column": "r"},
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {
            "function": "cumsum",
            "partition_by": ["g"],
            "order_by": ["o"],
            "target": "v",
            "new_column": "c",
        },
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {"function": "lag", "order_by": ["o"], "target": "v", "offset": 2, "new_column": "p"},
        {"in": "df_1"},
    ),
    ("windowFunction", {"function": "cumcount", "new_column": "n"}, {"in": "df_1"}),
    (
        "conditionalColumn",
        {
            "new_column": "tier",
            "default": "low",
            "rules": [
                {"column": "a", "operator": ">=", "value": 90, "result": "high"},
                {"column": "a", "operator": "contains", "value": "x", "result": "mid"},
            ],
        },
        {"in": "df_1"},
    ),
    (
        "mapValues",
        {
            "column": "a",
            "new_column": "b",
            "mapping": {"x": "y"},
            "default": "z",
            "use_default": True,
        },
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
        ("splitColumn", {"column": "a", "into": []}),  # empty into
        ("splitColumn", {"column": "a", "into": ["x"], "mode": "delimiter"}),  # no delimiter
        ("splitColumn", {"column": "a", "into": ["x"], "mode": "regex"}),  # no pattern
        ("parseDates", {"columns": []}),  # empty columns
        ("parseDates", {"columns": ["d"], "errors": "bogus"}),  # bad errors
        ("mapValues", {"column": "a"}),  # missing mapping
        ("mapValues", {"column": "a", "mapping": {}}),  # empty mapping
        ("windowFunction", {"function": "bogus", "new_column": "x"}),  # bad function
        ("windowFunction", {"function": "cumsum", "new_column": "x"}),  # cumsum needs target
        ("windowFunction", {"function": "rank", "new_column": "x"}),  # rank needs order_by
        ("windowFunction", {"function": "row_number"}),  # missing new_column
        ("conditionalColumn", {"rules": [{"column": "a", "value": 1}]}),  # missing new_column
        ("conditionalColumn", {"new_column": "x", "rules": []}),  # empty rules
        ("conditionalColumn", {"new_column": "x", "rules": [{"operator": "=="}]}),  # no column
        ("conditionalColumn", {"new_column": "x", "rules": [{"column": "a", "operator": ">"}]}),
    ],
)
def test_validate_rejects_bad_config(node_type, config):
    with pytest.raises(ValueError):
        get_transformation(node_type).validate_config(config)
