# SPDX-License-Identifier: AGPL-3.0-only
"""Chart nodes: render-ready chart data computed over the *full* frame at run time.

Each chart node is a pass-through (output frame == input frame) that computes an
aggregated, size-capped "chart artifact" — a small JSON document stored on the
run's NodeResult (``chart`` field). The run view renders the artifact directly,
so revisiting a run never recomputes the chart, and the chart reflects every row
the run processed rather than a preview sample.

All computation converts to pandas internally (like the assertion nodes) so the
logic stays engine-agnostic without widening EngineBackend. Artifacts must stay
small enough to live inside ``node_results_json``: every shape below caps its
category/point/series counts, and values are JSON-sanitized (NaN/inf -> None).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation, EmitsNodeMetadata, NodeMetadata

# Size caps. These bound the artifact JSON (stored in the run row) and keep the
# rendered chart readable; the artifact records the pre-cap totals so the UI can
# say "showing top N of M".
MAX_BAR_CATEGORIES = 50
DEFAULT_BAR_CATEGORIES = 25
MAX_STACK_SERIES = 8
MAX_PIE_SLICES = 12
DEFAULT_PIE_SLICES = 6
MAX_LINE_POINTS = 1000
MAX_LINE_SERIES = 8
MAX_SCATTER_POINTS = 2000
MAX_HISTOGRAM_BINS = 100
DEFAULT_HISTOGRAM_BINS = 20
MAX_BOX_GROUPS = 12
MAX_HEATMAP_COLUMNS = 12

VALID_AGGREGATES = ("sum", "mean", "count", "min", "max", "median")
BLANK_LABEL = "(blank)"
OTHER_LABEL = "Other"


def _finite(value: Any) -> float | None:
    """A JSON-safe float: None for NaN/inf/None, rounded so artifacts stay small."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, 6)


def _label(value: Any) -> str:
    """Category label for a raw cell value; blank-ish values share one bucket."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return BLANK_LABEL
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    text = str(value).strip()
    return text if text else BLANK_LABEL


def _numeric(pdf: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(pdf[column], errors="coerce")


def _require_columns(node_type: str, pdf: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c and c not in pdf.columns]
    if missing:
        raise ValueError(f"{node_type}: column(s) not found: {missing}")


def _category_values(
    pdf: pd.DataFrame,
    category: str,
    value: str | None,
    aggregate: str,
) -> pd.Series:
    """Per-category aggregated values. ``count`` counts rows (no value column
    needed); other aggregates coerce the value column to numeric."""
    labels = pdf[category].map(_label)
    if aggregate == "count" or not value:
        return labels.groupby(labels, sort=False).size()
    numbers = _numeric(pdf, value)
    grouped = numbers.groupby(labels, sort=False)
    aggregated: pd.Series = getattr(grouped, aggregate)()
    return aggregated


def _fold_other(
    pdf: pd.DataFrame,
    category: str,
    value: str | None,
    aggregate: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """Top-``limit`` categories plus a correct ``Other`` bucket.

    "Other" is recomputed from the raw rows (relabel + re-aggregate), not summed
    from the folded categories, so non-additive aggregates (mean, median) stay
    correct.
    """
    totals = _category_values(pdf, category, value, aggregate).sort_values(ascending=False)
    total_categories = len(totals)
    if total_categories <= limit:
        return (
            [{"label": str(k), "value": _finite(v)} for k, v in totals.items()],
            total_categories,
        )
    top = list(totals.index[:limit])
    labels = pdf[category].map(_label)
    folded_labels = labels.where(labels.isin(top), OTHER_LABEL)
    refolded = pdf.assign(**{"__chart_cat__": folded_labels})
    values = _category_values(refolded, "__chart_cat__", value, aggregate)
    data = [{"label": str(k), "value": _finite(values[k])} for k in top if k in values]
    if OTHER_LABEL in values.index:
        data.append({"label": OTHER_LABEL, "value": _finite(values[OTHER_LABEL])})
    return data, total_categories


def _stride_sample(items: list[Any], cap: int) -> list[Any]:
    """Deterministic even-stride downsample that always keeps first and last."""
    n = len(items)
    if n <= cap:
        return items
    step = (n - 1) / (cap - 1)
    picked = [items[round(i * step)] for i in range(cap)]
    picked[-1] = items[-1]
    return picked


def _x_sort_key(pdf: pd.DataFrame, x: str) -> pd.Series:
    """A sortable key for the x column: numeric if it coerces, datetime if it
    parses, otherwise the string labels themselves (source order preserved by a
    stable sort)."""
    numeric = pd.to_numeric(pdf[x], errors="coerce")
    if numeric.notna().mean() >= 0.8:
        return numeric
    as_dt = pd.to_datetime(pdf[x], errors="coerce", format="mixed")
    if as_dt.notna().mean() >= 0.8:
        return as_dt
    return pd.Series(range(len(pdf)), index=pdf.index)


class _BaseChart(BaseTransformation, EmitsNodeMetadata):
    """Shared skeleton: pass the frame through, attach the artifact as metadata.

    Codegen: a chart renders in the Ciaren run view only, so both generators emit
    a plain pass-through — the exported script's data logic is unaffected.
    """

    emits_metadata: bool = True

    #: Human label used in artifacts/comments; subclasses set it.
    chart_kind: str

    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]:
        frames, _ = self.execute_with_metadata(engine, inputs, config)
        return frames

    def execute_with_metadata(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> tuple[dict[str, AnyFrame], NodeMetadata | None]:
        df = inputs["in"]
        artifact = self._compute(engine.to_pandas(df), config)
        artifact["kind"] = self.chart_kind
        return {"out": df}, NodeMetadata(chart=artifact)

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"# {self.type}: chart is rendered in the Ciaren run view (no code equivalent)\n{dst} = {src}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return self.to_python_code(input_vars, output_vars, config)

    # -- shared config checks -------------------------------------------------

    def _check_aggregate(self, config: dict[str, Any], default: str) -> None:
        aggregate = config.get("aggregate") or default
        if aggregate not in VALID_AGGREGATES:
            raise ValueError(f"{self.type} 'aggregate' must be one of {', '.join(VALID_AGGREGATES)}")


# ---------------------------------------------------------------------------
# chartBar
# ---------------------------------------------------------------------------


class ChartBarTransformation(_BaseChart):
    """Aggregated bars per category, optionally stacked by a second column."""

    type = "chartBar"
    chart_kind = "bar"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("x"):
            raise ValueError("chartBar requires an 'x' (category) column")
        self._check_aggregate(config, "sum")
        aggregate = config.get("aggregate") or "sum"
        if aggregate != "count" and not config.get("y"):
            raise ValueError("chartBar requires a 'y' (value) column unless aggregate is 'count'")
        orientation = config.get("orientation") or "vertical"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError("chartBar 'orientation' must be 'vertical' or 'horizontal'")
        limit = config.get("limit")
        if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= MAX_BAR_CATEGORIES):
            raise ValueError(f"chartBar 'limit' must be an integer between 1 and {MAX_BAR_CATEGORIES}")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        x = config["x"]
        y = config.get("y") or None
        aggregate = config.get("aggregate") or "sum"
        if aggregate == "count":
            y = None
        group_by = config.get("group_by") or None
        limit = config.get("limit") or DEFAULT_BAR_CATEGORIES
        _require_columns(self.type, pdf, [x, y or "", group_by or ""])

        artifact: dict[str, Any] = {
            "x": x,
            "y": y,
            "aggregate": aggregate,
            "orientation": config.get("orientation") or "vertical",
            "rows_seen": int(len(pdf)),
        }

        if not group_by:
            data, total = _fold_other(pdf, x, y, aggregate, limit)
            artifact.update({"data": data, "total_categories": total})
            return artifact

        # Stacked: top categories by total, top series by total; the tail of the
        # *series* is folded into "Other" from raw rows so any aggregate is exact.
        cat_totals = _category_values(pdf, x, y, aggregate).sort_values(ascending=False)
        total_categories = len(cat_totals)
        cats = [str(k) for k in cat_totals.index[:limit]]

        series_labels = pdf[group_by].map(_label)
        series_totals = _category_values(pdf, group_by, y, aggregate).sort_values(ascending=False)
        total_series = len(series_totals)
        top_series = [str(k) for k in series_totals.index[: MAX_STACK_SERIES - 1]]
        if total_series > MAX_STACK_SERIES:
            series_labels = series_labels.where(series_labels.isin(top_series), OTHER_LABEL)
            series = [*top_series, OTHER_LABEL]
        else:
            series = [str(k) for k in series_totals.index]

        cat_labels = pdf[x].map(_label)
        work = pdf.assign(**{"__chart_cat__": cat_labels, "__chart_series__": series_labels})
        work = work[work["__chart_cat__"].isin(cats)]
        if aggregate == "count" or not y:
            table = work.groupby(["__chart_cat__", "__chart_series__"], sort=False).size()
        else:
            table = getattr(_numeric(work, y).groupby([work["__chart_cat__"], work["__chart_series__"]]), aggregate)()

        rows: list[dict[str, Any]] = []
        for cat in cats:
            row: dict[str, Any] = {"label": cat}
            for s in series:
                if (cat, s) in table.index:
                    row[s] = _finite(table[(cat, s)])
            rows.append(row)
        artifact.update(
            {
                "rows": rows,
                "series": series,
                "group_by": group_by,
                "total_categories": total_categories,
                "total_series": total_series,
            }
        )
        return artifact


# ---------------------------------------------------------------------------
# chartLine / chartArea
# ---------------------------------------------------------------------------


class ChartLineTransformation(_BaseChart):
    """One or more measures aggregated per x value, sorted along x."""

    type = "chartLine"
    chart_kind = "line"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("x"):
            raise ValueError(f"{self.type} requires an 'x' column")
        y_columns = config.get("y_columns")
        if not isinstance(y_columns, list) or not [c for c in y_columns if c]:
            raise ValueError(f"{self.type} requires at least one column in 'y_columns'")
        if len(y_columns) > MAX_LINE_SERIES:
            raise ValueError(f"{self.type} supports at most {MAX_LINE_SERIES} series")
        self._check_aggregate(config, "mean")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        x = config["x"]
        y_columns = [c for c in config.get("y_columns", []) if c]
        aggregate = config.get("aggregate") or "mean"
        _require_columns(self.type, pdf, [x, *y_columns])

        sort_key = _x_sort_key(pdf, x)
        ordered = pdf.assign(**{"__chart_sort__": sort_key}).sort_values("__chart_sort__", kind="stable")
        labels = ordered[x].map(_label)

        # Aggregate each y per x label, preserving x order of first appearance.
        seen: dict[str, dict[str, Any]] = {}
        for label in labels:
            if label not in seen:
                seen[label] = {"x": label}
        for y in y_columns:
            if aggregate == "count":
                agg = ordered.groupby(labels, sort=False).size()
            else:
                agg = getattr(_numeric(ordered, y).groupby(labels, sort=False), aggregate)()
            for label, value in agg.items():
                seen[str(label)][y] = _finite(value)

        points = list(seen.values())
        total_points = len(points)
        points = _stride_sample(points, MAX_LINE_POINTS)
        return {
            "x": x,
            "series": y_columns,
            "aggregate": aggregate,
            "rows": points,
            "total_points": total_points,
            "rows_seen": int(len(pdf)),
        }


class ChartAreaTransformation(ChartLineTransformation):
    """Same computation as the line chart, rendered with an area fill."""

    type = "chartArea"
    chart_kind = "area"


# ---------------------------------------------------------------------------
# chartScatter
# ---------------------------------------------------------------------------


class ChartScatterTransformation(_BaseChart):
    type = "chartScatter"
    chart_kind = "scatter"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("x") or not config.get("y"):
            raise ValueError("chartScatter requires numeric 'x' and 'y' columns")
        if config.get("x") == config.get("y"):
            raise ValueError("chartScatter 'x' and 'y' must be different columns")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        x, y = config["x"], config["y"]
        _require_columns(self.type, pdf, [x, y])
        xs = _numeric(pdf, x)
        ys = _numeric(pdf, y)
        mask = xs.notna() & ys.notna()
        pairs = [[_finite(a), _finite(b)] for a, b in zip(xs[mask], ys[mask], strict=True)]
        total_points = len(pairs)
        return {
            "x": x,
            "y": y,
            "points": _stride_sample(pairs, MAX_SCATTER_POINTS),
            "total_points": total_points,
            "rows_seen": int(len(pdf)),
        }


# ---------------------------------------------------------------------------
# chartPie
# ---------------------------------------------------------------------------


class ChartPieTransformation(_BaseChart):
    type = "chartPie"
    chart_kind = "pie"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("category"):
            raise ValueError("chartPie requires a 'category' column")
        self._check_aggregate(config, "count")
        aggregate = config.get("aggregate") or "count"
        if aggregate != "count" and not config.get("value"):
            raise ValueError("chartPie requires a 'value' column unless aggregate is 'count'")
        limit = config.get("limit")
        if limit is not None and (not isinstance(limit, int) or not 2 <= limit <= MAX_PIE_SLICES):
            raise ValueError(f"chartPie 'limit' must be an integer between 2 and {MAX_PIE_SLICES}")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        category = config["category"]
        aggregate = config.get("aggregate") or "count"
        value = None if aggregate == "count" else (config.get("value") or None)
        limit = config.get("limit") or DEFAULT_PIE_SLICES
        _require_columns(self.type, pdf, [category, value or ""])
        data, total = _fold_other(pdf, category, value, aggregate, limit)
        return {
            "category": category,
            "value": value,
            "aggregate": aggregate,
            "data": data,
            "total_categories": total,
            "rows_seen": int(len(pdf)),
        }


# ---------------------------------------------------------------------------
# chartHistogram
# ---------------------------------------------------------------------------


class ChartHistogramTransformation(_BaseChart):
    type = "chartHistogram"
    chart_kind = "histogram"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("chartHistogram requires a 'column'")
        bins = config.get("bins")
        if bins is not None and (not isinstance(bins, int) or not 1 <= bins <= MAX_HISTOGRAM_BINS):
            raise ValueError(f"chartHistogram 'bins' must be an integer between 1 and {MAX_HISTOGRAM_BINS}")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        column = config["column"]
        bins = config.get("bins") or DEFAULT_HISTOGRAM_BINS
        _require_columns(self.type, pdf, [column])
        values = _numeric(pdf, column).dropna()
        values = values[~values.isin([float("inf"), float("-inf")])]
        artifact: dict[str, Any] = {"column": column, "bins": bins, "rows_seen": int(len(pdf))}
        if values.empty:
            artifact["data"] = []
            return artifact
        lo, hi = float(values.min()), float(values.max())
        if lo == hi:
            artifact["data"] = [{"label": _format_edge(lo), "value": int(len(values))}]
            return artifact
        counts_arr, edges_arr = np.histogram(values.to_numpy(dtype=float), bins=bins)
        counts = [int(c) for c in counts_arr]
        edges = [float(e) for e in edges_arr]
        artifact["data"] = [
            {"label": f"{_format_edge(edges[i])} – {_format_edge(edges[i + 1])}", "value": counts[i]}
            for i in range(bins)
        ]
        return artifact


def _format_edge(v: float) -> str:
    """Compact bin-edge label matching the preview's style."""
    if v == 0:
        return "0"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# chartBoxPlot
# ---------------------------------------------------------------------------


class ChartBoxPlotTransformation(_BaseChart):
    type = "chartBoxPlot"
    chart_kind = "boxplot"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("chartBoxPlot requires a 'column' (numeric values)")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        column = config["column"]
        group_by = config.get("group_by") or None
        _require_columns(self.type, pdf, [column, group_by or ""])

        if group_by:
            groups = pdf[group_by].map(_label)
        else:
            groups = pd.Series([column] * len(pdf), index=pdf.index)
        values = _numeric(pdf, column)

        sizes = values.groupby(groups, sort=False).count().sort_values(ascending=False)
        total_groups = len(sizes)
        stats: list[dict[str, Any]] = []
        for name in sizes.index[:MAX_BOX_GROUPS]:
            vals = values[groups == name].dropna().sort_values()
            if vals.empty:
                continue
            q1, median, q3 = (float(vals.quantile(q)) for q in (0.25, 0.5, 0.75))
            iqr = q3 - q1
            lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            inside = vals[(vals >= lo_fence) & (vals <= hi_fence)]
            # Clamp so whiskers never sit inside the box: interpolated quantiles
            # on small groups can put q1/q3 beyond the nearest in-fence points.
            whisker_lo = min(float(inside.min()), q1) if not inside.empty else q1
            whisker_hi = max(float(inside.max()), q3) if not inside.empty else q3
            stats.append(
                {
                    "label": str(name),
                    "min": _finite(whisker_lo),
                    "q1": _finite(q1),
                    "median": _finite(median),
                    "q3": _finite(q3),
                    "max": _finite(whisker_hi),
                    "outliers": int(((vals < lo_fence) | (vals > hi_fence)).sum()),
                    "count": int(len(vals)),
                }
            )
        return {
            "column": column,
            "group_by": group_by,
            "groups": stats,
            "total_groups": total_groups,
            "rows_seen": int(len(pdf)),
        }


# ---------------------------------------------------------------------------
# chartHeatmap (correlation)
# ---------------------------------------------------------------------------


class ChartHeatmapTransformation(_BaseChart):
    type = "chartHeatmap"
    chart_kind = "heatmap"

    def validate_config(self, config: dict[str, Any]) -> None:
        columns = config.get("columns")
        if columns is not None and not isinstance(columns, list):
            raise ValueError("chartHeatmap 'columns' must be a list of column names")
        if isinstance(columns, list) and len([c for c in columns if c]) > MAX_HEATMAP_COLUMNS:
            raise ValueError(f"chartHeatmap supports at most {MAX_HEATMAP_COLUMNS} columns")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        chosen = [c for c in (config.get("columns") or []) if c]
        if chosen:
            _require_columns(self.type, pdf, chosen)
            numeric = pdf[chosen].apply(pd.to_numeric, errors="coerce")
        else:
            # Auto-selection considers real numbers and numeric-looking text, but
            # never datetimes — correlating nanosecond timestamps is meaningless.
            candidates = pdf.select_dtypes(exclude=["datetime", "datetimetz", "timedelta"])
            numeric = candidates.apply(pd.to_numeric, errors="coerce")
        # Keep columns that are usable as numbers, in frame order.
        usable = [c for c in numeric.columns if numeric[c].notna().mean() >= 0.5 and numeric[c].nunique() > 1]
        total_columns = len(usable)
        usable = usable[:MAX_HEATMAP_COLUMNS]
        if len(usable) < 2:
            raise ValueError("chartHeatmap needs at least two numeric columns to correlate")
        corr = numeric[usable].corr()
        matrix = [[_finite(corr.iloc[i, j]) for j in range(len(usable))] for i in range(len(usable))]
        return {
            "columns": [str(c) for c in usable],
            "matrix": matrix,
            "total_columns": total_columns,
            "rows_seen": int(len(pdf)),
        }
