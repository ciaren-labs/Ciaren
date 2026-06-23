"""Column profiling (app/engine/profile.py), exercised on both engines."""

import pandas as pd
import polars as pl
import pytest

from app.engine.backends import get_engine
from app.engine.profile import profile_frame


@pytest.fixture(params=["pandas", "polars"])
def engine(request):
    return get_engine(request.param)


def _native(engine, pdf: pd.DataFrame):
    return pl.from_pandas(pdf) if engine.name == "polars" else pdf


def _by_name(profiles):
    return {p["name"]: p for p in profiles}


def test_profiles_one_entry_per_column(engine):
    pdf = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    profiles = profile_frame(engine, _native(engine, pdf))
    assert {p["name"] for p in profiles} == {"a", "b"}
    for p in profiles:
        assert p["scanned"] == 3
        assert p["total"] == 3


def test_numeric_summary(engine):
    pdf = pd.DataFrame({"v": [1.0, 2.0, 3.0, None]})
    prof = _by_name(profile_frame(engine, _native(engine, pdf)))["v"]
    assert prof["dtype"] == "float"
    assert prof["null_count"] == 1
    assert prof["null_pct"] == 25.0
    assert prof["distinct"] == 3
    assert prof["min"] == 1.0
    assert prof["max"] == 3.0
    assert prof["mean"] == 2.0


def test_string_summary_top_values(engine):
    pdf = pd.DataFrame({"c": ["NYC", "NYC", "LA", None]})
    prof = _by_name(profile_frame(engine, _native(engine, pdf)))["c"]
    assert prof["dtype"] == "string"
    assert prof["null_count"] == 1
    assert prof["distinct"] == 2
    assert prof["min_len"] == 2  # "LA"
    assert prof["max_len"] == 3  # "NYC"
    top = {tv["value"]: tv["count"] for tv in prof["top_values"]}
    assert top["NYC"] == 2


def test_datetime_summary(engine):
    pdf = pd.DataFrame({"d": pd.to_datetime(["2021-01-01", "2021-06-15"])})
    prof = _by_name(profile_frame(engine, _native(engine, pdf)))["d"]
    assert prof["dtype"] == "datetime"
    assert "2021-01-01" in prof["min"]
    assert "2021-06-15" in prof["max"]


def test_all_null_column_has_no_summary(engine):
    pdf = pd.DataFrame({"a": pd.Series([None, None], dtype="float64")})
    prof = _by_name(profile_frame(engine, _native(engine, pdf)))["a"]
    assert prof["null_count"] == 2
    assert prof["distinct"] == 0
    assert "min" not in prof  # nothing to summarize


def test_sample_cap_limits_scanned_rows(engine):
    pdf = pd.DataFrame({"a": range(100)})
    profiles = profile_frame(engine, _native(engine, pdf), sample_cap=10)
    prof = profiles[0]
    assert prof["scanned"] == 10
    assert prof["total"] == 100
