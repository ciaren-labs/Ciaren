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


# -- additional branch coverage (both engines) ---------------------------


@pytest.mark.parametrize(
    "strategy,expected",
    [
        ("median", [1.0, 2.0, 3.0, 2.0]),
        ("min", [1.0, 1.0, 3.0, 1.0]),
        ("max", [1.0, 3.0, 3.0, 3.0]),
        ("zero", [1.0, 0.0, 3.0, 0.0]),
        ("ffill", [1.0, 1.0, 3.0, 3.0]),
    ],
)
def test_fill_nulls_strategies(engine, strategy, expected):
    pdf = pd.DataFrame({"a": [1.0, None, 3.0, None]})
    out = run(engine, "fillNulls", pdf, {"strategy": strategy, "columns": ["a"]})
    assert out["a"].tolist() == pytest.approx(expected)


def test_fill_nulls_bfill(engine):
    # bfill leaves a trailing null when nothing follows it.
    pdf = pd.DataFrame({"a": [1.0, None, 3.0, None]})
    out = run(engine, "fillNulls", pdf, {"strategy": "bfill", "columns": ["a"]})
    vals = out["a"].tolist()
    assert vals[:3] == pytest.approx([1.0, 3.0, 3.0])
    assert pd.isna(vals[3])


def test_remove_duplicates_keep_last(engine):
    pdf = pd.DataFrame({"b": ["x", "y", "y", "z"], "c": [1, 2, 3, 4]})
    out = run(engine, "removeDuplicates", pdf, {"subset": ["b"], "keep": "last"})
    assert sorted(out["c"].tolist()) == [1, 3, 4]


def test_remove_duplicates_keep_false_drops_all_dupes(engine):
    pdf = pd.DataFrame({"b": ["x", "y", "y", "z"], "c": [1, 2, 3, 4]})
    out = run(engine, "removeDuplicates", pdf, {"subset": ["b"], "keep": False})
    assert sorted(out["c"].tolist()) == [1, 4]


@pytest.mark.parametrize("how,expected_rows", [("left", 3), ("right", 3), ("outer", 4)])
def test_join_how_variants(engine, how, expected_rows):
    left = pd.DataFrame({"id": [1, 2, 3], "x": ["a", "b", "c"]})
    right = pd.DataFrame({"id": [1, 2, 4], "y": ["p", "q", "r"]})
    out = run(
        engine, "join", None, {"on": ["id"], "how": how}, inputs={"left": left, "right": right}
    )
    assert len(out) == expected_rows
    # an 'on' join keeps a single key column on every engine (no duplicate 'id_y').
    assert sorted(out.columns) == ["id", "x", "y"]


def test_join_custom_suffixes(engine):
    left = pd.DataFrame({"id": [1, 2], "v": [10, 20]})
    right = pd.DataFrame({"id": [1, 2], "v": [30, 40]})
    out = run(
        engine,
        "join",
        None,
        {"on": ["id"], "how": "inner", "suffixes": ["_L", "_R"]},
        inputs={"left": left, "right": right},
    )
    # left-side overlap keeps its name; the right-side overlap gets the suffix.
    assert "v_R" in out.columns


@pytest.mark.parametrize(
    "function,target,expected",
    [
        ("cummax", "v", [5, 5, 9, 9]),
        ("cummin", "v", [5, 1, 1, 1]),
    ],
)
def test_window_cumulative_variants(engine, function, target, expected):
    pdf = pd.DataFrame({"o": [1, 2, 3, 4], "v": [5, 1, 9, 3]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {"function": function, "order_by": ["o"], "target": target, "new_column": "r"},
    )
    assert out["r"].tolist() == expected


def test_window_dense_rank(engine):
    pdf = pd.DataFrame({"s": [10, 10, 20, 30]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {"function": "dense_rank", "order_by": ["s"], "new_column": "r"},
    )
    assert out["r"].tolist() == [1, 1, 2, 3]


def test_window_cumcount_unpartitioned(engine):
    pdf = pd.DataFrame({"x": [10, 20, 30]})
    out = run(engine, "windowFunction", pdf, {"function": "cumcount", "new_column": "n"})
    assert out["n"].tolist() == [0, 1, 2]


def test_window_lead(engine):
    pdf = pd.DataFrame({"o": [1, 2, 3, 4], "v": [5, 1, 9, 3]})
    out = run(
        engine,
        "windowFunction",
        pdf,
        {"function": "lead", "order_by": ["o"], "target": "v", "offset": 1, "new_column": "nxt"},
    )
    vals = out["nxt"].tolist()
    assert vals[:3] == [1, 9, 3]
    assert pd.isna(vals[3])


@pytest.mark.parametrize(
    "operation,data,expected",
    [
        ("lower", ["AbC"], ["abc"]),
        ("upper", ["AbC"], ["ABC"]),
        ("strip", ["  hi  "], ["hi"]),
        ("title", ["hello world"], ["Hello World"]),
        ("capitalize", ["hello WORLD"], ["Hello world"]),
    ],
)
def test_string_simple_ops(engine, operation, data, expected):
    pdf = pd.DataFrame({"s": data})
    out = run(engine, "stringTransform", pdf, {"column": "s", "operation": operation})
    assert out["s"].tolist() == expected


def test_extract_date_parts_weekday_and_hour(engine):
    # 2021-03-15 is a Monday -> weekday 0 (pandas convention) on both engines.
    pdf = pd.DataFrame({"d": pd.to_datetime(["2021-03-15 13:00", "2021-03-21 09:00"])})
    out = run(engine, "extractDateParts", pdf, {"column": "d", "parts": ["weekday", "day", "hour"]})
    assert out["d_weekday"].tolist() == [0, 6]  # Monday=0, Sunday=6
    assert out["d_day"].tolist() == [15, 21]
    assert out["d_hour"].tolist() == [13, 9]


def test_map_values_in_place(engine):
    pdf = pd.DataFrame({"g": ["A", "B", "C"]})
    out = run(engine, "mapValues", pdf, {"column": "g", "mapping": {"A": "1", "B": "2"}})
    assert out["g"].tolist() == ["1", "2", "C"]


def test_conditional_column_isnull(engine):
    pdf = pd.DataFrame({"v": [1.0, None, 3.0]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "flag",
            "default": "has",
            "rules": [{"column": "v", "operator": "isnull", "result": "missing"}],
        },
    )
    assert out["flag"].tolist() == ["has", "missing", "has"]


def test_conditional_column_numeric_value(engine):
    # numeric value compared against a numeric column works on both engines.
    pdf = pd.DataFrame({"score": [95, 75, 40]})
    out = run(
        engine,
        "conditionalColumn",
        pdf,
        {
            "new_column": "grade",
            "default": "F",
            "rules": [{"column": "score", "operator": ">=", "value": 90, "result": "A"}],
        },
    )
    assert out["grade"].tolist() == ["A", "F", "F"]


def test_pivot_str_index_and_count(engine):
    pdf = pd.DataFrame({"r": ["x", "x", "y"], "c": ["m", "n", "m"], "v": [1, 2, 3]})
    out = run(engine, "pivot", pdf, {"index": "r", "columns": "c", "values": "v", "aggfunc": "count"})
    assert "m" in out.columns and "n" in out.columns


def test_unpivot_value_vars_subset(engine):
    pdf = pd.DataFrame({"id": [1], "a": [10], "b": [20], "c": [30]})
    out = run(engine, "unpivot", pdf, {"id_vars": ["id"], "value_vars": ["a", "b"]})
    assert sorted(out["variable"].tolist()) == ["a", "b"]
    assert "c" not in out["variable"].tolist()


def test_bin_column_with_labels(engine):
    pdf = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    out = run(
        engine,
        "binColumn",
        pdf,
        {"column": "x", "new_column": "bucket", "method": "equalwidth", "bins": 2,
         "labels": ["low", "high"]},
    )
    assert set(out["bucket"].dropna().tolist()) <= {"low", "high"}


def test_remove_outliers_iqr_clip(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 100.0]})
    out = run(engine, "removeOutliers", pdf, {"columns": ["v"], "method": "iqr", "action": "clip"})
    assert len(out) == 4  # clip keeps all rows
    assert max(out["v"].tolist()) < 100.0


def test_remove_outliers_zscore_drop(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 2.0, 100.0]})
    out = run(
        engine,
        "removeOutliers",
        pdf,
        {"columns": ["v"], "method": "zscore", "action": "drop", "threshold": 1},
    )
    assert 100.0 not in out["v"].tolist()


def test_remove_outliers_percentile_clip(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, 100.0]})
    out = run(
        engine,
        "removeOutliers",
        pdf,
        {"columns": ["v"], "method": "percentile", "action": "clip", "lower": 0, "upper": 75},
    )
    assert len(out) == 4
    assert max(out["v"].tolist()) < 100.0


def test_cast_boolean(engine):
    pdf = pd.DataFrame({"flag": [1, 0, 1]})
    out = run(engine, "castDtypes", pdf, {"casts": {"flag": "boolean"}})
    assert out["flag"].tolist() == [True, False, True]


@pytest.mark.parametrize("op,value,expected", [
    ("contains", "a", ["cat", "bat"]),
    ("startswith", "c", ["cat"]),
    ("endswith", "g", ["dog"]),
])
def test_filter_string_operators(engine, op, value, expected):
    pdf = pd.DataFrame({"s": ["cat", "dog", "bat"]})
    out = run(engine, "filterRows", pdf, {"column": "s", "operator": op, "value": value})
    assert sorted(out["s"].tolist()) == sorted(expected)


def test_concat_rows_both_engines(engine):
    pdf = pd.DataFrame({"a": [1, 2]})
    out = run(engine, "concatRows", pdf, {}, inputs={"in": pdf, "in_1": pdf})
    assert len(out) == 4


def test_calculated_column_both_engines(engine):
    pdf = pd.DataFrame({"price": [2, 3], "qty": [4, 5]})
    out = run(engine, "calculatedColumn", pdf, {"column_name": "total", "expression": "price * qty"})
    assert out["total"].tolist() == [8, 15]


def test_replace_values_literal_both_engines(engine):
    pdf = pd.DataFrame({"b": ["x", "y", "y", "z"]})
    out = run(engine, "replaceValues", pdf, {"column": "b", "to_replace": "y", "value": "Y"})
    assert out["b"].tolist() == ["x", "Y", "Y", "z"]


@pytest.mark.parametrize(
    "func,expected",
    [
        ("sum", 40.0),
        ("min", 20.0),
        ("max", 20.0),
        ("median", 20.0),
        ("count", 2),
        ("nunique", 1),
    ],
)
def test_groupby_aggregations(engine, func, expected):
    pdf = pd.DataFrame({"g": ["a", "a", "b"], "v": [20.0, 20.0, 5.0]})
    out = run(engine, "groupByAggregate", pdf, {"group_by": ["g"], "aggregations": {"v": func}})
    row = out[out["g"] == "a"]["v"].tolist()[0]
    assert row == pytest.approx(expected)


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
    # regression branches: outer join coalesce, capitalize, weekday, more windows
    ("join", {"on": ["a"], "how": "outer"}, {"left": "df_1", "right": "df_0"}),
    ("stringTransform", {"column": "a", "operation": "capitalize"}, {"in": "df_1"}),
    ("stringTransform", {"column": "a", "operation": "title"}, {"in": "df_1"}),
    ("stringTransform", {"column": "a", "operation": "strip"}, {"in": "df_1"}),
    ("extractDateParts", {"column": "d", "parts": ["weekday", "day", "hour"]}, {"in": "df_1"}),
    (
        "windowFunction",
        {"function": "dense_rank", "order_by": ["o"], "new_column": "r"},
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {"function": "cummax", "order_by": ["o"], "target": "v", "new_column": "r"},
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {"function": "cummin", "order_by": ["o"], "target": "v", "new_column": "r"},
        {"in": "df_1"},
    ),
    (
        "windowFunction",
        {"function": "lead", "order_by": ["o"], "target": "v", "offset": 1, "new_column": "r"},
        {"in": "df_1"},
    ),
    ("conditionalColumn", {
        "new_column": "f", "default": "x",
        "rules": [{"column": "a", "operator": "isnull", "result": "missing"}],
    }, {"in": "df_1"}),
    ("fillNulls", {"strategy": "zero", "columns": ["a"]}, {"in": "df_1"}),
    ("fillNulls", {"strategy": "bfill"}, {"in": "df_1"}),
    ("fillNulls", {"strategy": "min", "columns": ["a"]}, {"in": "df_1"}),
    ("fillNulls", {"strategy": "max", "columns": ["a"]}, {"in": "df_1"}),
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
        ("conditionalColumn", {  # bad match keyword
            "new_column": "x",
            "rules": [{"match": "some", "conditions": [{"column": "a", "operator": ">", "value": 1}]}],
        }),
        ("conditionalColumn", {  # unknown operator
            "new_column": "x",
            "rules": [{"column": "a", "operator": "~=", "value": 1, "result": "y"}],
        }),
        ("windowFunction", {"function": "lag", "order_by": ["o"], "target": "v",
                            "offset": 0, "new_column": "x"}),  # offset < 1
        ("windowFunction", {"function": "dense_rank", "new_column": "x"}),  # rank needs order_by
        ("removeDuplicates", {"keep": "middle"}),  # bad keep
        ("sortRows", {"columns": ["a"], "na_position": "center"}),  # bad na_position
        ("fillNulls", {"strategy": "constant"}),  # constant needs value
        ("pivot", {"index": ["r"], "columns": "c"}),  # missing values
        ("sampleRows", {"n": -1}),  # negative n
        ("binColumn", {"column": "x", "bins": 3}),  # missing new_column
    ],
)
def test_validate_rejects_bad_config(node_type, config):
    with pytest.raises(ValueError):
        get_transformation(node_type).validate_config(config)
