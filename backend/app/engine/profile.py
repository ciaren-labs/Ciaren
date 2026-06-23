"""Per-column profiling for preview panels and dataset views.

Computes lightweight, type-aware statistics (null counts, distinct counts, and
numeric/string/datetime summaries) on a bounded sample so it stays cheap on
large frames. Engine-agnostic: it converts via the backend's ``to_pandas`` and
summarizes with pandas, so pandas and polars frames profile identically.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.engine.backends.base import AnyFrame, EngineBackend

# Cap rows scanned for stats so profiling stays fast on large frames.
PROFILE_SAMPLE_CAP = 10_000
# How many top values to report for low-cardinality (string) columns.
TOP_VALUES = 5


def profile_frame(engine: EngineBackend, df: AnyFrame, sample_cap: int = PROFILE_SAMPLE_CAP) -> list[dict[str, Any]]:
    """Return one profile dict per column.

    Stats are computed over at most ``sample_cap`` rows; each profile records the
    ``scanned`` vs ``total`` row counts so the UI can flag when sampling kicked in.
    """
    total = int(engine.row_count(df))
    pdf = engine.to_pandas(df)
    if total > sample_cap:
        pdf = pdf.head(sample_cap)
    scanned = len(pdf)
    return [_profile_column(pdf[col], str(col), scanned, total) for col in pdf.columns]


def _profile_column(series: pd.Series, name: str, scanned: int, total: int) -> dict[str, Any]:
    null_count = int(series.isna().sum())
    non_null = series.dropna()
    profile: dict[str, Any] = {
        "name": name,
        "dtype": _dtype_label(series),
        "null_count": null_count,
        "null_pct": round(null_count / scanned * 100, 2) if scanned else 0.0,
        "distinct": int(non_null.nunique()),
        "scanned": scanned,
        "total": total,
    }
    if not len(non_null):
        return profile

    if pd.api.types.is_bool_dtype(series):
        profile["true_count"] = int(non_null.sum())
    elif pd.api.types.is_numeric_dtype(series):
        profile["min"] = _num(non_null.min())
        profile["max"] = _num(non_null.max())
        profile["mean"] = _num(non_null.mean())
        profile["std"] = _num(non_null.std())
    elif pd.api.types.is_datetime64_any_dtype(series):
        profile["min"] = str(non_null.min())
        profile["max"] = str(non_null.max())
    else:
        text = non_null.astype("string")
        lengths = text.str.len()
        profile["min_len"] = int(lengths.min())
        profile["max_len"] = int(lengths.max())
        top = text.value_counts().head(TOP_VALUES)
        profile["top_values"] = [{"value": str(value), "count": int(count)} for value, count in top.items()]
    return profile


def _dtype_label(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _num(value: Any) -> float | None:
    """JSON-safe numeric: NaN/NaT → None, everything else a rounded float."""
    return None if pd.isna(value) else round(float(value), 4)
