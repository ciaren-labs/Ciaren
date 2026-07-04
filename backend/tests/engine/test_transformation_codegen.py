"""Branch coverage for transformation code generation and config validation.

Every transformation emits both pandas (``to_python_code``) and polars
(``to_polars_code``) source. These tests drive each node's generators across all
their branches and assert the emitted code is at least syntactically valid, plus
exercise the ``validate_config`` rejection paths that the happy-path tests skip.
"""

import pytest

from app.engine.registry import get_transformation


def _vars(node_type: str) -> tuple[dict[str, str], dict[str, str]]:
    if node_type == "join":
        return {"left": "left_df", "right": "right_df"}, {"out": "out_df"}
    if node_type == "concatRows":
        return {"in": "df0", "in_1": "df1"}, {"out": "out_df"}
    return {"in": "df"}, {"out": "out_df"}


# (test id, node_type, config) — chosen to hit each generator branch.
CODEGEN_CASES = [
    # filterRows: one case per operator family
    ("filter_eq", "filterRows", {"column": "a", "operator": "==", "value": 1}),
    ("filter_isnull", "filterRows", {"column": "a", "operator": "isnull"}),
    ("filter_notnull", "filterRows", {"column": "a", "operator": "notnull"}),
    ("filter_between", "filterRows", {"column": "a", "operator": "between", "value": 1, "value2": 9}),
    ("filter_in_str", "filterRows", {"column": "a", "operator": "in", "value": "x, y"}),
    ("filter_in_list", "filterRows", {"column": "a", "operator": "in", "value": ["x", "y"]}),
    ("filter_contains", "filterRows", {"column": "a", "operator": "contains", "value": "z"}),
    # regex-special value: each engine's own semantics (pandas regex, polars literal)
    # must survive into the generated code.
    ("filter_contains_dot", "filterRows", {"column": "a", "operator": "contains", "value": "z.b"}),
    # non-string value: the engines coerce with str(); the emitters must too.
    ("filter_contains_numeric", "filterRows", {"column": "a", "operator": "contains", "value": 5}),
    ("filter_startswith", "filterRows", {"column": "a", "operator": "startswith", "value": "z"}),
    ("filter_endswith", "filterRows", {"column": "a", "operator": "endswith", "value": "z"}),
    # sortRows: default and the na_position / per-column-direction branch
    ("sort_default", "sortRows", {"columns": ["a"]}),
    ("sort_multi", "sortRows", {"columns": ["a", "b"], "ascending": [True, False], "na_position": "first"}),
    # limitRows: head vs slice
    ("limit_head", "limitRows", {"n": 5}),
    ("limit_offset", "limitRows", {"n": 5, "offset": 2}),
    # sampleRows: frac vs n
    ("sample_frac", "sampleRows", {"frac": 0.5, "seed": 1}),
    ("sample_n", "sampleRows", {"n": 3, "seed": 1}),
    # removeDuplicates: with/without subset
    ("dedupe_default", "removeDuplicates", {}),
    ("dedupe_subset", "removeDuplicates", {"subset": ["a"], "keep": "last"}),
    # column ops
    ("drop_cols", "dropColumns", {"columns": ["a"]}),
    ("rename_cols", "renameColumns", {"mapping": {"a": "b"}}),
    ("select_cols", "selectColumns", {"columns": ["a"]}),
    # castDtypes: datetime (with fmt+coerce), numeric coerce, plain
    ("cast_dt", "castDtypes", {"casts": {"a": "datetime"}, "format": "%Y-%m-%d", "errors": "coerce"}),
    ("cast_dt_datetime", "castDtypes", {"casts": {"d": "datetime"}}),
    ("cast_int_coerce", "castDtypes", {"casts": {"a": "integer"}, "errors": "coerce"}),
    ("cast_plain", "castDtypes", {"casts": {"a": "string"}}),
    # dropNulls: any/all, with/without subset
    ("dropnull_any", "dropNulls", {}),
    ("dropnull_any_subset", "dropNulls", {"subset": ["a"]}),
    ("dropnull_all", "dropNulls", {"how": "all"}),
    ("dropnull_all_subset", "dropNulls", {"how": "all", "subset": ["a"]}),
    # fillNulls: constant (±columns), direct strategy (±columns), median, mode
    ("fill_const", "fillNulls", {"value": 0}),
    ("fill_const_cols", "fillNulls", {"value": 0, "columns": ["a"]}),
    ("fill_ffill", "fillNulls", {"strategy": "ffill"}),
    ("fill_ffill_cols", "fillNulls", {"strategy": "ffill", "columns": ["a"]}),
    ("fill_mean", "fillNulls", {"strategy": "mean"}),
    ("fill_mean_cols", "fillNulls", {"strategy": "mean", "columns": ["a"]}),
    ("fill_median", "fillNulls", {"strategy": "median", "columns": ["a"]}),
    ("fill_median_all_null", "fillNulls", {"strategy": "median"}),
    ("fill_mode", "fillNulls", {"strategy": "mode", "columns": ["a"]}),
    ("fill_mode_multimodal", "fillNulls", {"strategy": "mode", "columns": ["a"]}),
    # reshape / compute
    ("groupby", "groupByAggregate", {"group_by": ["a"], "aggregations": {"b": "sum"}}),
    ("concat", "concatRows", {}),
    ("calc", "calculatedColumn", {"column_name": "d", "expression": "a + b"}),
    # date coercion nodes: the engines dispatch on the column's dtype at runtime
    # (parse strings, cast already-temporal columns), and the input dtype depends
    # on upstream nodes — so each node gets a string-input AND a datetime-input
    # case, and the emitters must reproduce the dispatch in the generated code.
    ("dateparts", "extractDateParts", {"column": "d", "parts": ["year", "month", "day", "weekday", "hour"]}),
    ("dateparts_str", "extractDateParts", {"column": "a", "parts": ["year", "month", "day", "weekday", "hour"]}),
    ("parse_dates", "parseDates", {"columns": ["a"]}),
    ("parse_dates_fmt", "parseDates", {"columns": ["a"], "format": "%Y-%m-%d", "errors": "raise"}),
    ("parse_dates_datetime", "parseDates", {"columns": ["d"]}),
    ("date_diff", "dateDifference", {"start_column": "s", "end_column": "e", "unit": "hours", "new_column": "diff"}),
    (
        "date_diff_datetime",
        "dateDifference",
        {"start_column": "s", "end_column": "e", "unit": "days", "new_column": "diff"},
    ),
    ("unpivot_min", "unpivot", {"id_vars": ["id"]}),
    ("unpivot_full", "unpivot", {"id_vars": ["id"], "value_vars": ["x"], "var_name": "k", "value_name": "v"}),
    ("pivot_str_index", "pivot", {"index": "r", "columns": "c", "values": "v"}),
    ("pivot_count", "pivot", {"index": ["r"], "columns": "c", "values": "v", "aggfunc": "count"}),
    # text
    ("replace_literal", "replaceValues", {"column": "a", "to_replace": "x", "value": "y"}),
    ("replace_regex", "replaceValues", {"column": "a", "to_replace": "x+", "value": "y", "regex": True}),
    ("str_upper", "stringTransform", {"column": "a", "operation": "upper"}),
    ("str_replace", "stringTransform", {"column": "a", "operation": "replace", "find": "x", "replace_with": "y"}),
    (
        "str_pad_right",
        "stringTransform",
        {"column": "a", "operation": "pad", "width": 5, "side": "right", "fill_char": "0"},
    ),
    ("str_pad_left", "stringTransform", {"column": "a", "operation": "pad", "width": 5}),
    # numeric
    ("outlier_iqr_drop", "removeOutliers", {"columns": ["a"], "method": "iqr", "action": "drop"}),
    ("outlier_z_clip", "removeOutliers", {"columns": ["a"], "method": "zscore", "action": "clip"}),
    ("outlier_pct_drop", "removeOutliers", {"columns": ["a"], "method": "percentile", "action": "drop"}),
    ("round", "roundNumbers", {"columns": ["a"], "decimals": 2}),
    ("bin_equal", "binColumn", {"column": "a", "new_column": "b", "method": "equalwidth", "bins": 3}),
    ("bin_quantile", "binColumn", {"column": "a", "new_column": "b", "method": "quantile", "bins": 4}),
    # join: on vs left_on/right_on with custom suffixes
    ("join_on", "join", {"on": "id", "how": "inner"}),
    ("join_split", "join", {"left_on": "lid", "right_on": "rid", "how": "left", "suffixes": ["_l", "_r"]}),
]


@pytest.mark.parametrize("node_type,config", [(c[1], c[2]) for c in CODEGEN_CASES], ids=[c[0] for c in CODEGEN_CASES])
def test_codegen_branches_compile(node_type: str, config: dict) -> None:
    t = get_transformation(node_type)
    t.validate_config(config)
    in_vars, out_vars = _vars(node_type)
    py = t.to_python_code(in_vars, out_vars, config)
    pl_code = t.to_polars_code(in_vars, out_vars, config)
    compile(py, "<pandas>", "exec")
    compile(pl_code, "<polars>", "exec")


def test_filter_codegen_unknown_operator_raises() -> None:
    t = get_transformation("filterRows")
    in_vars, out_vars = _vars("filterRows")
    cfg = {"column": "a", "operator": "weird", "value": 1}
    with pytest.raises(ValueError, match="Unknown filter operator"):
        t.to_python_code(in_vars, out_vars, cfg)
    with pytest.raises(ValueError, match="Unknown filter operator"):
        t.to_polars_code(in_vars, out_vars, cfg)


# -- validate_config rejection branches ---------------------------------

VALIDATE_ERRORS = [
    ("filterRows", {"column": "a", "operator": "=="}),  # missing value
    ("sortRows", {}),  # missing columns
    ("sortRows", {"columns": ["a"], "na_position": "middle"}),  # bad na_position
    ("limitRows", {"n": 1, "offset": -1}),  # negative offset
    ("sampleRows", {"frac": 5}),  # frac out of (0, 1]
    ("sampleRows", {}),  # neither n nor frac
    ("removeDuplicates", {"keep": "bogus"}),  # bad keep
    ("groupByAggregate", {"aggregations": {"a": "sum"}}),  # missing group_by
    ("calculatedColumn", {"expression": "a + 1"}),  # missing column_name
    ("extractDateParts", {"parts": ["year"]}),  # missing column
    ("extractDateParts", {"column": "d"}),  # missing parts
    ("extractDateParts", {"column": "d", "parts": ["century"]}),  # invalid part
    ("replaceValues", {}),  # missing column
    ("replaceValues", {"column": "a"}),  # missing to_replace/value
    ("stringTransform", {"operation": "upper"}),  # missing column
    ("stringTransform", {"column": "a", "operation": "replace"}),  # replace without find
    ("stringTransform", {"column": "a", "operation": "pad"}),  # pad without width
    ("removeOutliers", {"columns": ["a"], "method": "bogus"}),  # bad method
    ("removeOutliers", {"columns": ["a"], "action": "bogus"}),  # bad action
    ("roundNumbers", {"columns": ["a"], "decimals": "x"}),  # decimals not int
    ("binColumn", {"column": "a"}),  # missing new_column
    ("binColumn", {"column": "a", "new_column": "b", "bins": 1}),  # bins < 2
    ("binColumn", {"column": "a", "new_column": "b", "bins": 3, "method": "bogus"}),  # bad method
    ("join", {"on": "id", "how": "bogus"}),  # bad how
    ("dropNulls", {"how": "sometimes"}),  # bad how
    ("castDtypes", {"casts": {"a": "blob"}}),  # unknown dtype
]


@pytest.mark.parametrize("node_type,config", VALIDATE_ERRORS)
def test_validate_config_rejects(node_type: str, config: dict) -> None:
    with pytest.raises(ValueError):
        get_transformation(node_type).validate_config(config)


def test_join_custom_suffixes_in_codegen() -> None:
    t = get_transformation("join")
    in_vars, out_vars = _vars("join")
    cfg = {"on": "id", "how": "outer", "suffixes": ["_l", "_r"]}
    assert "_l" in t.to_python_code(in_vars, out_vars, cfg)
    assert "_r" in t.to_polars_code(in_vars, out_vars, cfg)
