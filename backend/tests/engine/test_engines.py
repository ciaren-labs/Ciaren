"""Cross-engine behaviour tests.

Every backend must produce equivalent results, so the same assertions run
against both pandas and polars via parametrization. Results are normalised to
pandas (``engine.to_pandas``) before comparison.
"""

import pandas as pd
import pytest

from app.engine.backends import available_engines, get_engine

ENGINES = available_engines()


@pytest.fixture(params=ENGINES)
def engine(request):
    return get_engine(request.param)


@pytest.fixture
def frame(engine):
    pdf = pd.DataFrame(
        {
            "id": [1, 2, 3, 3],
            "group": ["a", "a", "b", "b"],
            "value": [10.0, 20.0, 30.0, 30.0],
        }
    )
    # Convert to the engine's native frame type.
    return _to_native(engine, pdf)


def _to_native(engine, pdf):
    if engine.name == "polars":
        import polars as pl

        return pl.from_pandas(pdf)
    return pdf


def test_row_count(engine, frame):
    assert engine.row_count(frame) == 4


def test_to_records(engine, frame):
    records = engine.to_records(frame, n=2)
    assert len(records) == 2
    assert records[0]["id"] == 1


def test_rename_columns(engine, frame):
    out = engine.to_pandas(engine.rename_columns(frame, {"value": "amount"}))
    assert "amount" in out.columns


def test_drop_columns(engine, frame):
    out = engine.to_pandas(engine.drop_columns(frame, ["group"]))
    assert list(out.columns) == ["id", "value"]


def test_select_columns(engine, frame):
    out = engine.to_pandas(engine.select_columns(frame, ["id"]))
    assert list(out.columns) == ["id"]


def test_filter_rows(engine, frame):
    out = engine.to_pandas(engine.filter_rows(frame, "value", ">", 15))
    assert out["value"].min() > 15


def test_drop_duplicates(engine, frame):
    out = engine.to_pandas(engine.drop_duplicates(frame, ["id"], "first"))
    assert len(out) == 3


def test_sort_rows(engine, frame):
    out = engine.to_pandas(engine.sort_rows(frame, ["value"], [False]))
    assert out["value"].tolist()[0] == 30.0


def test_cast_column(engine, frame):
    out = engine.to_pandas(engine.cast_column(frame, "id", "string"))
    assert str(out["id"].dtype) in {"object", "string", "str"}


def test_add_column(engine, frame):
    out = engine.to_pandas(engine.add_column(frame, "double", "value * 2"))
    assert out["double"].tolist() == [20.0, 40.0, 60.0, 60.0]


def test_groupby_agg(engine, frame):
    out = engine.to_pandas(engine.groupby_agg(frame, ["group"], {"value": "sum"}))
    by_group = out.set_index("group")["value"].to_dict()
    assert by_group == {"a": 30.0, "b": 60.0}


def test_fill_nulls(engine):
    pdf = pd.DataFrame({"a": [1.0, None, 3.0]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.fill_nulls(frame, None, "constant", 0))
    assert out["a"].tolist() == [1.0, 0.0, 3.0]


def test_fill_nulls_mean_strategy(engine):
    pdf = pd.DataFrame({"a": [1.0, None, 3.0]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.fill_nulls(frame, None, "mean", None))
    assert out["a"].tolist() == [1.0, 2.0, 3.0]


def test_fill_nulls_ffill_strategy(engine):
    pdf = pd.DataFrame({"a": [1.0, None, 3.0]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.fill_nulls(frame, None, "ffill", None))
    assert out["a"].tolist() == [1.0, 1.0, 3.0]


def test_filter_rows_between(engine):
    pdf = pd.DataFrame({"a": [1, 5, 10, 15]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.filter_rows(frame, "a", "between", [5, 10]))
    assert out["a"].tolist() == [5, 10]


def test_filter_rows_in(engine):
    pdf = pd.DataFrame({"a": ["x", "y", "z"]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.filter_rows(frame, "a", "in", ["x", "z"]))
    assert out["a"].tolist() == ["x", "z"]


def test_drop_nulls(engine):
    pdf = pd.DataFrame({"a": [1.0, None, 3.0]})
    frame = _to_native(get_engine(engine.name), pdf)
    out = engine.to_pandas(engine.drop_nulls(frame, None))
    assert len(out) == 2


def test_join(engine):
    left = _to_native(engine, pd.DataFrame({"id": [1, 2], "x": ["a", "b"]}))
    right = _to_native(engine, pd.DataFrame({"id": [1, 2], "y": ["c", "d"]}))
    out = engine.to_pandas(engine.join(left, right, ["id"], "inner"))
    assert len(out) == 2
    assert "x" in out.columns and "y" in out.columns


def test_concat(engine, frame):
    out = engine.to_pandas(engine.concat([frame, frame]))
    assert len(out) == 8


def test_limit_rows(engine, frame):
    out = engine.to_pandas(engine.limit_rows(frame, 2))
    assert len(out) == 2


def test_replace_values(engine, frame):
    out = engine.to_pandas(engine.replace_values(frame, "group", "a", "z"))
    assert sorted(out["group"].unique()) == ["b", "z"]


def test_string_transform(engine, frame):
    out = engine.to_pandas(engine.string_transform(frame, "group", "upper"))
    assert set(out["group"]) == {"A", "B"}


def test_csv_roundtrip(engine, frame, tmp_path):
    path = tmp_path / "data.csv"
    engine.write(frame, str(path), "csv")
    loaded = engine.to_pandas(engine.read(str(path), "csv"))
    assert engine.row_count(frame) == len(loaded)
