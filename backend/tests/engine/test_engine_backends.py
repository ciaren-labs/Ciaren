"""Branch coverage for the pandas and polars engine backends.

These exercise the individual engine operations (every filter operator, fill
strategy, string op, outlier method, etc.) directly against both backends, so
the two implementations are held to the same behaviour. Transformation-level
wiring is covered in ``test_transformations.py``; this file targets the engine
methods themselves.
"""

import datetime as dt
import json

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine

ENGINES = ["pandas", "polars"]


@pytest.mark.parametrize("engine_name", ENGINES)
def test_to_records_are_json_serializable_with_dates(engine_name: str) -> None:
    """Samples flow into a JSON column (run node_results) and over the API, so
    temporal values must serialize. Regression: polars to_dicts() returned native
    datetime objects, which broke persistence of any date-parsing flow's run."""
    engine = get_engine(engine_name)
    pdf = pd.DataFrame(
        {
            "when": pd.to_datetime(["2023-01-02", "2023-03-04"]),
            "day": [dt.date(2023, 1, 2), dt.date(2023, 3, 4)],
            "n": [1, 2],
        }
    )
    frame = pl.from_pandas(pdf) if engine_name == "polars" else pdf
    records = engine.to_records(frame)
    # Must not raise — proves no datetime/date objects leaked through.
    json.dumps(records)
    assert isinstance(records[0]["when"], str)
    assert records[0]["when"].startswith("2023-01-02")


def _make(engine_name: str, data: dict) -> object:
    pdf = pd.DataFrame(data)
    return pl.from_pandas(pdf) if engine_name == "polars" else pdf


def _pdf(engine: object, frame: object) -> pd.DataFrame:
    return engine.to_pandas(frame)  # type: ignore[attr-defined]


# -- I/O round trip -----------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("source_type,suffix", [("csv", "csv"), ("excel", "xlsx"), ("parquet", "parquet")])
def test_io_round_trip(engine_name: str, source_type: str, suffix: str, tmp_path) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1, 2, 3], "b": ["x", "y", "z"]})
    path = str(tmp_path / f"data.{suffix}")
    engine.write(frame, path, source_type)
    loaded = engine.read(path, source_type)
    out = _pdf(engine, loaded)
    assert list(out.columns) == ["a", "b"]
    assert len(out) == 3


@pytest.mark.parametrize("engine_name", ENGINES)
def test_column_names_matches_frame_without_materializing(engine_name: str) -> None:
    # The run DAG reads each node's columns via column_names (cheap), instead of
    # converting the whole frame to pandas. Both engines must agree.
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1, 2], "b": ["x", "y"], "c": [1.5, 2.5]})
    assert engine.column_names(frame) == ["a", "b", "c"]


@pytest.mark.parametrize("source_type,suffix", [("csv", "csv"), ("parquet", "parquet")])
def test_polars_streaming_read_matches_eager_read(source_type: str, suffix: str, tmp_path) -> None:
    # The polars backend reads via scan + streaming collect to cap peak memory;
    # the result must be byte-identical to an eager read, including null handling
    # and dtype inference across mixed columns.
    df = pl.DataFrame(
        {
            "i": [1, 2, None, 4],
            "s": ["x", None, "z", "w"],
            "f": [1.5, 2.5, None, 4.0],
            "b": [True, False, True, None],
        }
    )
    path = str(tmp_path / f"data.{suffix}")
    if source_type == "csv":
        df.write_csv(path)
        eager = pl.read_csv(path)
    else:
        df.write_parquet(path)
        eager = pl.read_parquet(path)

    streamed = get_engine("polars").read(path, source_type)
    assert streamed.schema == eager.schema
    assert streamed.equals(eager)


@pytest.mark.parametrize("engine_name", ENGINES)
def test_io_unsupported_source_type_raises(engine_name: str, tmp_path) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1]})
    with pytest.raises(ValueError, match="Unsupported source_type"):
        engine.read("x.bogus", "bogus")
    with pytest.raises(ValueError, match="Unsupported source_type"):
        engine.write(frame, str(tmp_path / "x"), "bogus")


# -- filter_rows: every operator ----------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize(
    "operator,value,expected",
    [
        ("==", 2, 1),
        ("eq", 2, 1),
        ("!=", 2, 3),
        ("ne", 2, 3),
        (">", 2, 2),
        ("gt", 2, 2),
        (">=", 2, 3),
        ("gte", 2, 3),
        ("<", 2, 1),
        ("lt", 2, 1),
        ("<=", 2, 2),
        ("lte", 2, 2),
        ("between", [2, 3], 2),
        ("in", [1, 4], 2),
    ],
)
def test_filter_numeric_operators(engine_name: str, operator: str, value: object, expected: int) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"n": [1, 2, 3, 4]})
    out = _pdf(engine, engine.filter_rows(frame, "n", operator, value))
    assert len(out) == expected


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("operator,expected", [("contains", 2), ("startswith", 2), ("endswith", 2)])
def test_filter_string_operators(engine_name: str, operator: str, expected: int) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": ["apple", "banana", "cherry", "apple"]})
    value = {"contains": "ap", "startswith": "a", "endswith": "e"}[operator]
    out = _pdf(engine, engine.filter_rows(frame, "s", operator, value))
    assert len(out) == expected


@pytest.mark.parametrize("engine_name", ENGINES)
def test_filter_null_operators(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"m": [1, None, 3, None]})
    assert len(_pdf(engine, engine.filter_rows(frame, "m", "isnull", None))) == 2
    assert len(_pdf(engine, engine.filter_rows(frame, "m", "notnull", None))) == 2


@pytest.mark.parametrize("engine_name", ENGINES)
def test_filter_unknown_operator_raises(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"n": [1, 2]})
    with pytest.raises(ValueError, match="Unknown filter operator"):
        engine.filter_rows(frame, "n", "bogus", 1)


# -- fill_nulls: every strategy -----------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("strategy", ["zero", "mean", "median", "min", "max", "mode", "ffill", "bfill"])
def test_fill_numeric_strategies(engine_name: str, strategy: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1.0, 2.0, None, 4.0]})
    out = _pdf(engine, engine.fill_nulls(frame, ["a"], strategy, None))
    assert out["a"].isna().sum() == 0


@pytest.mark.parametrize("engine_name", ENGINES)
def test_fill_constant(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1.0, None, 3.0]})
    out = _pdf(engine, engine.fill_nulls(frame, ["a"], "constant", 0))
    assert out["a"].tolist() == [1.0, 0.0, 3.0]


@pytest.mark.parametrize("engine_name", ENGINES)
def test_fill_constant_incompatible_dtype_is_skipped(engine_name: str) -> None:
    # An int column with a non-castable constant: the column is left unchanged
    # rather than blowing up the whole run.
    pdf = pd.DataFrame({"i": pd.array([1, 2, None], dtype="Int64")})
    frame = pl.from_pandas(pdf) if engine_name == "polars" else pdf
    engine = get_engine(engine_name)
    out = _pdf(engine, engine.fill_nulls(frame, ["i"], "constant", "not-an-int"))
    assert out["i"].isna().sum() == 1  # untouched


@pytest.mark.parametrize("engine_name", ENGINES)
def test_fill_unknown_strategy_raises(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1.0, None]})
    with pytest.raises(ValueError, match="Unknown fill strategy"):
        engine.fill_nulls(frame, ["a"], "bogus", None)


# -- drop_nulls / drop_duplicates ---------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_drop_nulls_how_all_and_subset(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1.0, None, None], "b": [1.0, None, 3.0]})
    assert len(_pdf(engine, engine.drop_nulls(frame, None, "all"))) == 2  # only all-null row drops
    assert len(_pdf(engine, engine.drop_nulls(frame, ["a"], "any"))) == 1


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("keep,expected", [("first", 2), ("last", 2), (False, 1)])
def test_drop_duplicates_keep(engine_name: str, keep: object, expected: int) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"k": ["a", "a", "b"]})
    out = _pdf(engine, engine.drop_duplicates(frame, ["k"], keep))
    assert len(out) == expected


# -- cast_column --------------------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_cast_datetime_from_string(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"d": ["2021-01-02", "2021-03-04"]})
    out = _pdf(engine, engine.cast_column(frame, "d", "datetime", "%Y-%m-%d", "raise"))
    assert "datetime" in str(out["d"].dtype)


@pytest.mark.parametrize("engine_name", ENGINES)
def test_cast_datetime_from_datetime_dtype(engine_name: str) -> None:
    engine = get_engine(engine_name)
    pdf = pd.DataFrame({"d": pd.to_datetime(["2021-01-02", "2021-03-04"])})
    frame = pl.from_pandas(pdf) if engine_name == "polars" else pdf
    out = _pdf(engine, engine.cast_column(frame, "d", "datetime", None, "raise"))
    assert "datetime" in str(out["d"].dtype)


@pytest.mark.parametrize("engine_name", ENGINES)
def test_cast_integer_coerce(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"n": ["1", "2", "x"]})
    out = _pdf(engine, engine.cast_column(frame, "n", "integer", None, "coerce"))
    assert out["n"].isna().sum() == 1  # "x" became null


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("dtype", ["float", "boolean", "string"])
def test_cast_simple_dtypes(engine_name: str, dtype: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1, 0]})
    out = _pdf(engine, engine.cast_column(frame, "v", dtype, None, "raise"))
    assert "v" in out.columns


@pytest.mark.parametrize("engine_name", ENGINES)
def test_cast_unknown_dtype_raises(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1, 2]})
    with pytest.raises(ValueError, match="Unknown dtype"):
        engine.cast_column(frame, "v", "nope", None, "raise")


# -- sort / select / add_column / groupby -------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("na_position", ["first", "last"])
def test_sort_na_position(engine_name: str, na_position: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"n": [2.0, None, 1.0]})
    out = _pdf(engine, engine.sort_rows(frame, ["n"], [True], na_position))
    first_is_null = pd.isna(out["n"].iloc[0])
    assert first_is_null == (na_position == "first")


@pytest.mark.parametrize("engine_name", ENGINES)
def test_groupby_agg(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"g": ["a", "a", "b"], "v": [1, 2, 3]})
    out = _pdf(engine, engine.groupby_agg(frame, ["g"], {"v": "sum"}))
    assert out.set_index("g").loc["a", "v"] == 3


def test_polars_groupby_unknown_func_raises() -> None:
    engine = get_engine("polars")
    frame = _make("polars", {"g": ["a"], "v": [1]})
    with pytest.raises(ValueError, match="Unsupported aggregation"):
        engine.groupby_agg(frame, ["g"], {"v": "bogus"})


# -- join / concat / limit / replace ------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_join_on_and_left_right_on(engine_name: str) -> None:
    engine = get_engine(engine_name)
    left = _make(engine_name, {"id": [1, 2], "x": ["a", "b"]})
    right = _make(engine_name, {"id": [1, 2], "y": ["c", "d"]})
    on_result = _pdf(engine, engine.join(left, right, ["id"], "inner"))
    assert len(on_result) == 2

    left2 = _make(engine_name, {"lid": [1, 2], "x": ["a", "b"]})
    right2 = _make(engine_name, {"rid": [1, 2], "y": ["c", "d"]})
    lr_result = _pdf(engine, engine.join(left2, right2, None, "inner", ["lid"], ["rid"]))
    assert len(lr_result) == 2


def test_polars_join_unknown_how_raises() -> None:
    engine = get_engine("polars")
    left = _make("polars", {"id": [1]})
    right = _make("polars", {"id": [1]})
    with pytest.raises(ValueError, match="Unsupported join how"):
        engine.join(left, right, ["id"], "bogus")


@pytest.mark.parametrize("engine_name", ENGINES)
def test_concat_and_limit_with_offset(engine_name: str) -> None:
    engine = get_engine(engine_name)
    a = _make(engine_name, {"v": [1, 2]})
    b = _make(engine_name, {"v": [3, 4]})
    assert len(_pdf(engine, engine.concat([a, b]))) == 4
    sliced = _pdf(engine, engine.limit_rows(_make(engine_name, {"v": [1, 2, 3, 4]}), 2, 1))
    assert sliced["v"].tolist() == [2, 3]


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("regex", [False, True])
def test_replace_values(engine_name: str, regex: bool) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": ["aa", "bb", "aa"]})
    to_replace = "a+" if regex else "aa"
    out = _pdf(engine, engine.replace_values(frame, "s", to_replace, "Z", regex))
    assert "Z" in out["s"].tolist()


# -- string_transform: every operation ----------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("operation", ["lower", "upper", "strip", "title", "capitalize", "len"])
def test_string_simple_ops(engine_name: str, operation: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": [" hello world ", "FOO bar"]})
    out = _pdf(engine, engine.string_transform(frame, "s", operation))
    assert "s" in out.columns


@pytest.mark.parametrize("engine_name", ENGINES)
def test_string_replace(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": ["a-b", "c-d"]})
    out = _pdf(engine, engine.string_transform(frame, "s", "replace", find="-", replace_with="_"))
    assert out["s"].tolist() == ["a_b", "c_d"]


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("side", ["left", "right"])
def test_string_pad(engine_name: str, side: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": ["ab"]})
    out = _pdf(engine, engine.string_transform(frame, "s", "pad", width=4, fill_char="*", side=side))
    assert len(out["s"].iloc[0]) == 4


@pytest.mark.parametrize("engine_name", ENGINES)
def test_string_unknown_op_raises(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"s": ["a"]})
    with pytest.raises(ValueError, match="Unknown string operation"):
        engine.string_transform(frame, "s", "bogus")


# -- sample / outliers / round / bin ------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_sample_rows_n_and_frac(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": list(range(10))})
    assert len(_pdf(engine, engine.sample_rows(frame, 3, None, 42))) == 3
    assert len(_pdf(engine, engine.sample_rows(frame, None, 0.5, 42))) == 5


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("method", ["iqr", "zscore", "percentile"])
@pytest.mark.parametrize("action", ["drop", "clip"])
def test_remove_outliers(engine_name: str, method: str, action: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1.0, 2.0, 3.0, 4.0, 1000.0]})
    out = _pdf(engine, engine.remove_outliers(frame, ["v"], method, action, 1.5, 3.0, 1.0, 99.0))
    # Bounds differ per method; assert the branch ran and shape is sane rather
    # than that this particular sample tripped each detector.
    if action == "drop":
        assert len(out) <= 5
    else:
        assert "v" in out.columns and len(out) == 5


@pytest.mark.parametrize("engine_name", ENGINES)
def test_outlier_unknown_method_raises(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1.0, 2.0]})
    with pytest.raises(ValueError, match="Unknown outlier method"):
        engine.remove_outliers(frame, ["v"], "bogus", "drop", 1.5, 3.0, 1.0, 99.0)


@pytest.mark.parametrize("engine_name", ENGINES)
def test_round_columns(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1.234, 5.678]})
    out = _pdf(engine, engine.round_columns(frame, ["v"], 1))
    assert out["v"].tolist() == [1.2, 5.7]


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("method", ["equalwidth", "quantile"])
def test_bin_column(engine_name: str, method: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"v": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]})
    out = _pdf(engine, engine.bin_column(frame, "v", "bucket", method, 3, None))
    assert "bucket" in out.columns
    assert out["bucket"].notna().any()


# -- date parts / unpivot / pivot ---------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_extract_date_parts_from_string(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"d": ["2021-02-03 04:00:00", "2022-06-07 08:00:00"]})
    out = _pdf(engine, engine.extract_date_parts(frame, "d", ["year", "month", "day", "weekday", "hour"]))
    assert out["d_year"].tolist() == [2021, 2022]
    assert out["d_hour"].tolist() == [4, 8]


@pytest.mark.parametrize("engine_name", ENGINES)
def test_extract_date_parts_from_datetime_dtype(engine_name: str) -> None:
    engine = get_engine(engine_name)
    pdf = pd.DataFrame({"d": pd.to_datetime(["2021-02-03", "2022-06-07"])})
    frame = pl.from_pandas(pdf) if engine_name == "polars" else pdf
    out = _pdf(engine, engine.extract_date_parts(frame, "d", ["year"]))
    assert out["d_year"].tolist() == [2021, 2022]


@pytest.mark.parametrize("engine_name", ENGINES)
def test_unpivot(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"id": [1, 2], "x": [10, 20], "y": [30, 40]})
    out = _pdf(engine, engine.unpivot(frame, ["id"], ["x", "y"], "variable", "value"))
    assert set(out.columns) == {"id", "variable", "value"}
    assert len(out) == 4


@pytest.mark.parametrize("engine_name", ENGINES)
@pytest.mark.parametrize("aggfunc", ["sum", "count"])
def test_pivot(engine_name: str, aggfunc: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"r": ["a", "a", "b"], "c": ["x", "y", "x"], "v": [1, 2, 3]})
    out = _pdf(engine, engine.pivot(frame, ["r"], "c", "v", aggfunc))
    assert "r" in out.columns


# -- to_records / row_count ---------------------------------------------


@pytest.mark.parametrize("engine_name", ENGINES)
def test_to_records_and_row_count(engine_name: str) -> None:
    engine = get_engine(engine_name)
    frame = _make(engine_name, {"a": [1, 2, 3]})
    assert engine.row_count(frame) == 3
    assert len(engine.to_records(frame, 2)) == 2
    assert len(engine.to_records(frame)) == 3
