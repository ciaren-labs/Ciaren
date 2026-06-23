import pandas as pd
import pytest

from app.engine.backends import get_engine
from app.engine.registry import get_transformation, list_transformation_types


@pytest.fixture
def engine():
    return get_engine("pandas")


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "a": [1, 2, 2, None],
            "b": ["x", "y", "y", "z"],
            "c": [10.0, 20.0, 20.0, 40.0],
        }
    )


def run(node_type, engine, inputs, config):
    t = get_transformation(node_type)
    t.validate_config(config)
    return t.execute(engine, inputs, config)["out"]


def test_registry_contains_expected_types():
    types = set(list_transformation_types())
    assert {"dropNulls", "castDtypes", "join", "concatRows"} <= types


def test_drop_nulls(engine, df):
    out = run("dropNulls", engine, {"in": df}, {})
    assert len(out) == 3


def test_drop_nulls_subset(engine, df):
    out = run("dropNulls", engine, {"in": df}, {"subset": ["b"]})
    assert len(out) == 4


def test_fill_nulls_all(engine, df):
    out = run("fillNulls", engine, {"in": df}, {"value": 0})
    assert out["a"].isna().sum() == 0


def test_fill_nulls_columns(engine, df):
    out = run("fillNulls", engine, {"in": df}, {"value": 0, "columns": ["a"]})
    assert out["a"].tolist() == [1, 2, 2, 0]


def test_fill_nulls_mean_strategy(engine, df):
    out = run("fillNulls", engine, {"in": df}, {"strategy": "mean", "columns": ["a"]})
    # mean of [1, 2, 2] = 5/3
    assert out["a"].tolist() == pytest.approx([1, 2, 2, 5 / 3])


def test_fill_nulls_mode_strategy(engine, df):
    out = run("fillNulls", engine, {"in": df}, {"strategy": "mode", "columns": ["a"]})
    assert out["a"].tolist() == [1, 2, 2, 2]  # mode is 2


def test_fill_nulls_strategy_needs_no_value(engine, df):
    # The 'constant' default needs a value, but a strategy does not.
    get_transformation("fillNulls").validate_config({"strategy": "median"})


def test_fill_nulls_bad_strategy_rejected():
    with pytest.raises(ValueError):
        get_transformation("fillNulls").validate_config({"strategy": "bogus"})


def test_drop_columns(engine, df):
    out = run("dropColumns", engine, {"in": df}, {"columns": ["c"]})
    assert list(out.columns) == ["a", "b"]


def test_rename_columns(engine, df):
    out = run("renameColumns", engine, {"in": df}, {"mapping": {"a": "alpha"}})
    assert "alpha" in out.columns


def test_select_columns(engine, df):
    out = run("selectColumns", engine, {"in": df}, {"columns": ["a"]})
    assert list(out.columns) == ["a"]


def test_remove_duplicates(engine, df):
    out = run("removeDuplicates", engine, {"in": df}, {"subset": ["b"]})
    assert len(out) == 3


def test_filter_rows_numeric(engine, df):
    out = run("filterRows", engine, {"in": df}, {"column": "c", "operator": ">", "value": 15})
    assert out["c"].min() > 15


def test_filter_rows_isnull(engine, df):
    out = run("filterRows", engine, {"in": df}, {"column": "a", "operator": "isnull"})
    assert len(out) == 1


def test_filter_rows_between(engine, df):
    out = run(
        "filterRows",
        engine,
        {"in": df},
        {"column": "c", "operator": "between", "value": 15, "value2": 25},
    )
    assert out["c"].tolist() == [20.0, 20.0]


def test_filter_rows_between_needs_value2():
    with pytest.raises(ValueError):
        get_transformation("filterRows").validate_config({"column": "c", "operator": "between", "value": 1})


def test_filter_rows_in(engine, df):
    out = run(
        "filterRows",
        engine,
        {"in": df},
        {"column": "b", "operator": "in", "value": "x, z"},
    )
    assert out["b"].tolist() == ["x", "z"]


def test_sort_rows(engine, df):
    out = run("sortRows", engine, {"in": df}, {"columns": ["c"], "ascending": False})
    assert out["c"].tolist()[0] == 40.0


def test_cast_dtypes(engine, df):
    out = run("castDtypes", engine, {"in": df}, {"casts": {"b": "string"}})
    assert str(out["b"].dtype) == "string"


def test_cast_dtypes_invalid_dtype(engine, df):
    with pytest.raises(ValueError):
        run("castDtypes", engine, {"in": df}, {"casts": {"b": "nope"}})


def test_calculated_column(engine, df):
    out = run("calculatedColumn", engine, {"in": df}, {"column_name": "d", "expression": "c * 2"})
    assert out["d"].tolist() == [20.0, 40.0, 40.0, 80.0]


def test_group_by_aggregate(engine, df):
    out = run(
        "groupByAggregate",
        engine,
        {"in": df},
        {"group_by": ["b"], "aggregations": {"c": "sum"}},
    )
    assert out.set_index("b").loc["y", "c"] == 40.0


def test_concat_rows(engine, df):
    out = run("concatRows", engine, {"in": df, "in_1": df}, {})
    assert len(out) == 8


def test_join(engine):
    left = pd.DataFrame({"id": [1, 2], "x": ["a", "b"]})
    right = pd.DataFrame({"id": [1, 2], "y": ["c", "d"]})
    out = run("join", engine, {"left": left, "right": right}, {"on": "id", "how": "inner"})
    assert list(out.columns) == ["id", "x", "y"]
    assert len(out) == 2


def test_limit_rows(engine, df):
    out = run("limitRows", engine, {"in": df}, {"n": 2})
    assert len(out) == 2


def test_replace_values(engine, df):
    out = run("replaceValues", engine, {"in": df}, {"column": "b", "to_replace": "y", "value": "Y"})
    assert out["b"].tolist() == ["x", "Y", "Y", "z"]


def test_string_transform_upper(engine, df):
    out = run("stringTransform", engine, {"in": df}, {"column": "b", "operation": "upper"})
    assert out["b"].tolist() == ["X", "Y", "Y", "Z"]


def test_string_transform_invalid_op(engine, df):
    with pytest.raises(ValueError):
        run("stringTransform", engine, {"in": df}, {"column": "b", "operation": "reverse"})


@pytest.mark.parametrize(
    "node_type,config",
    [
        ("dropColumns", {}),
        ("limitRows", {"n": -1}),
        ("replaceValues", {"column": "a"}),
        ("stringTransform", {"column": "a", "operation": "bogus"}),
        ("renameColumns", {}),
        ("selectColumns", {"columns": []}),
        ("fillNulls", {}),
        ("filterRows", {"column": "a"}),
        ("castDtypes", {}),
        ("groupByAggregate", {"group_by": ["b"]}),
        ("calculatedColumn", {"column_name": "d"}),
        ("join", {}),
    ],
)
def test_validate_config_rejects_bad_config(node_type, config):
    with pytest.raises(ValueError):
        get_transformation(node_type).validate_config(config)
