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
category/point/series counts AND label lengths, and values are JSON-sanitized
(NaN/inf -> None).

Two data-driven collisions are defended against throughout:
- The fold bucket is computed under a sentinel label so a *genuine* category
  named "Other" can never merge with (or double-count against) folded rows.
- Row dicts reserve the keys ``"label"`` (stacked bars) and ``"x"`` (line/area);
  a series whose name collides gets a zero-width space appended, which is
  invisible in legends but keeps the payload unambiguous.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
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
#: Longest label/name stored in an artifact. Labels come from data, so without a
#: cap a long-text column would bloat node_results_json (loaded on every run GET).
MAX_LABEL_LEN = 120
#: Longest user-provided chart title stored in an artifact.
MAX_TITLE_LEN = 200
#: Rows sampled to decide which columns are numeric enough for the heatmap.
HEATMAP_DETECT_SAMPLE = 10_000

VALID_AGGREGATES = ("sum", "mean", "count", "min", "max", "median")
BLANK_LABEL = "(blank)"
OTHER_LABEL = "Other"
#: Fold-bucket label when a *real* category named "Other" is also on the chart.
OTHER_FALLBACK_LABEL = "Other (rest)"
#: Internal sentinel for the fold bucket — never emitted, so it cannot collide
#: with a genuine category value (``_label`` strips cell text, so a leading NUL
#: can never survive into a real label). No trailing NUL: numpy's fixed-width
#: unicode arrays silently strip those, which would corrupt the sentinel.
_OTHER_SENTINEL = "\x00__ciaren_other__"


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


def _short(text: str) -> str:
    return text if len(text) <= MAX_LABEL_LEN else f"{text[: MAX_LABEL_LEN - 1]}…"


def _is_na_scalar(value: Any) -> bool:
    """pd.isna for a single cell, tolerating list-like cells (never NA)."""
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict, np.ndarray)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _label(value: Any) -> str:
    """Category label for a raw cell value; blank-ish values (None, NaN, NaT,
    pd.NA, whitespace) share one bucket, and labels are length-capped."""
    if _is_na_scalar(value):
        return BLANK_LABEL
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    # NULs are dropped so no real label can ever equal the fold sentinel (and
    # NUL inside JSON text breaks Postgres storage anyway).
    text = str(value).replace("\x00", "").strip()
    return _short(text) if text else BLANK_LABEL


def _safe_key(name: str, reserved: frozenset[str]) -> str:
    """A dict key for a data-derived series name that cannot shadow a reserved
    artifact key. The zero-width space is invisible in the rendered legend."""
    return name + "\u200b" if name in reserved else name


def _numeric(pdf: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(pdf[column], errors="coerce")


def _require_columns(node_type: str, pdf: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c and c not in pdf.columns]
    if missing:
        raise ValueError(f"{node_type}: column(s) not found: {missing}")


def _check_int(node_type: str, name: str, value: Any, lo: int, hi: int) -> None:
    """Reject a non-int (bools included — bool is an int subclass) or out-of-range
    integer option."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise ValueError(f"{node_type} {name!r} must be an integer between {lo} and {hi}")


def _category_values(
    pdf: pd.DataFrame,
    category: str,
    value: str | None,
    aggregate: str,
    labels: pd.Series | None = None,
) -> pd.Series:
    """Per-category aggregated values. ``count`` counts rows (no value column
    needed); other aggregates coerce the value column to numeric. ``labels``
    lets callers pass pre-computed (possibly folded) labels."""
    if labels is None:
        labels = pdf[category].map(_label)
    if aggregate == "count" or not value:
        return labels.groupby(labels, sort=False).size()
    numbers = _numeric(pdf, value)
    grouped = numbers.groupby(labels, sort=False)
    aggregated: pd.Series = getattr(grouped, aggregate)()
    return aggregated


def _fold_display_label(top: list[str]) -> str:
    """What the fold bucket is called on the chart: "Other", unless a genuine
    category with that exact name is also shown."""
    return OTHER_FALLBACK_LABEL if OTHER_LABEL in top else OTHER_LABEL


def _fold_other(
    pdf: pd.DataFrame,
    category: str,
    value: str | None,
    aggregate: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """Top-``limit`` categories plus a correct fold bucket.

    The fold bucket is recomputed from the raw rows (relabel + re-aggregate)
    under an uncollidable sentinel, so non-additive aggregates (mean, median)
    stay correct and a genuine "Other" category is neither merged nor emitted
    twice.
    """
    labels = pdf[category].map(_label)
    totals = _category_values(pdf, category, value, aggregate, labels=labels).sort_values(ascending=False)
    total_categories = len(totals)
    if total_categories <= limit:
        return (
            [{"label": str(k), "value": _finite(v)} for k, v in totals.items()],
            total_categories,
        )
    top = [str(k) for k in totals.index[:limit]]
    folded_labels = labels.where(labels.isin(top), _OTHER_SENTINEL)
    values = _category_values(pdf, category, value, aggregate, labels=folded_labels)
    data = [{"label": k, "value": _finite(values[k])} for k in top if k in values.index]
    if _OTHER_SENTINEL in values.index:
        data.append({"label": _fold_display_label(top), "value": _finite(values[_OTHER_SENTINEL])})
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

    In preview the artifact is skipped entirely — preview only needs the frames,
    and computing (then discarding) aggregations over the full data on every
    downstream preview would be pure waste (mirrors the ML nodes' short-circuit).

    Codegen: a chart renders in the Ciaren run view only, so both generators emit
    a plain pass-through — the exported script's data logic is unaffected.
    """

    emits_metadata: bool = True

    #: Artifact ``kind`` discriminator; subclasses set it.
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
        if in_preview():
            return {"out": df}, None
        artifact = self._compute(engine.to_pandas(df), config)
        artifact["kind"] = self.chart_kind
        title = str(config.get("title") or "").strip()
        if title:
            artifact["title"] = title[:MAX_TITLE_LEN]
        return {"out": df}, NodeMetadata(chart=artifact)

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"# {self.type}: chart is rendered in the Ciaren run view (no code equivalent)\n{dst} = {src}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return self.to_python_code(input_vars, output_vars, config)

    # -- shared config checks -------------------------------------------------

    def validate_config(self, config: dict[str, Any]) -> None:
        title = config.get("title")
        if title is not None and not isinstance(title, str):
            raise ValueError(f"{self.type} 'title' must be a string")

    def _check_aggregate(self, config: dict[str, Any], default: str) -> None:
        aggregate = config.get("aggregate") or default
        if aggregate not in VALID_AGGREGATES:
            raise ValueError(f"{self.type} 'aggregate' must be one of {', '.join(VALID_AGGREGATES)}.")


# ---------------------------------------------------------------------------
# chartBar
# ---------------------------------------------------------------------------


class ChartBarTransformation(_BaseChart):
    """Aggregated bars per category, optionally stacked by a second column."""

    type = "chartBar"
    chart_kind = "bar"

    def validate_config(self, config: dict[str, Any]) -> None:
        super().validate_config(config)
        if not config.get("x"):
            raise ValueError(f"{self.type} requires an 'x' column.")
        self._check_aggregate(config, "sum")
        aggregate = config.get("aggregate") or "sum"
        if aggregate != "count" and not config.get("y"):
            raise ValueError(f"{self.type} requires a 'y' column unless aggregate is 'count'.")
        orientation = config.get("orientation") or "vertical"
        if orientation not in ("vertical", "horizontal"):
            raise ValueError(f"{self.type} 'orientation' must be 'vertical' or 'horizontal'.")
        _check_int(self.type, "limit", config.get("limit"), 1, MAX_BAR_CATEGORIES)

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
            "x": _short(x),
            "y": _short(y) if y else None,
            "aggregate": aggregate,
            "orientation": config.get("orientation") or "vertical",
            "rows_seen": int(len(pdf)),
        }

        if not group_by:
            data, total = _fold_other(pdf, x, y, aggregate, limit)
            artifact.update({"data": data, "total_categories": total})
            return artifact

        # Stacked: top categories by total (tail folded into "Other" like the
        # plain-bar path) and top series by total (tail folded likewise). Both
        # folds re-aggregate raw rows under sentinels, so any aggregate is exact
        # and genuine "Other" values can't merge or double-count.
        cat_labels = pdf[x].map(_label)
        cat_totals = _category_values(pdf, x, y, aggregate, labels=cat_labels).sort_values(ascending=False)
        total_categories = len(cat_totals)
        top_cats = [str(k) for k in cat_totals.index[:limit]]
        if total_categories > limit:
            cat_labels = cat_labels.where(cat_labels.isin(top_cats), _OTHER_SENTINEL)
            cat_display = {_OTHER_SENTINEL: _fold_display_label(top_cats)}
            cats = [*top_cats, _OTHER_SENTINEL]
        else:
            cat_display = {}
            cats = top_cats

        series_labels = pdf[group_by].map(_label)
        series_totals = _category_values(pdf, group_by, y, aggregate, labels=series_labels).sort_values(ascending=False)
        total_series = len(series_totals)
        if total_series > MAX_STACK_SERIES:
            top_series = [str(k) for k in series_totals.index[: MAX_STACK_SERIES - 1]]
            series_labels = series_labels.where(series_labels.isin(top_series), _OTHER_SENTINEL)
            series_display = {_OTHER_SENTINEL: _fold_display_label(top_series)}
            series_ids = [*top_series, _OTHER_SENTINEL]
        else:
            series_display = {}
            series_ids = [str(k) for k in series_totals.index]

        # "label" is the reserved category key on each row; a series *named*
        # "label" is stored under an invisible-suffix key instead.
        key_for = {s: _safe_key(series_display.get(s, s), frozenset({"label"})) for s in series_ids}

        work = pdf.assign(**{"__chart_cat__": cat_labels, "__chart_series__": series_labels})
        if aggregate == "count" or not y:
            table = work.groupby(["__chart_cat__", "__chart_series__"], sort=False).size()
        else:
            table = getattr(_numeric(work, y).groupby([work["__chart_cat__"], work["__chart_series__"]]), aggregate)()

        rows: list[dict[str, Any]] = []
        for cat in cats:
            row: dict[str, Any] = {"label": cat_display.get(cat, cat)}
            for s in series_ids:
                if (cat, s) in table.index:
                    row[key_for[s]] = _finite(table[(cat, s)])
            rows.append(row)
        artifact.update(
            {
                "rows": rows,
                "series": [key_for[s] for s in series_ids],
                "group_by": _short(group_by),
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
        super().validate_config(config)
        if not config.get("x"):
            raise ValueError(f"{self.type} requires an 'x' column.")
        y_columns = config.get("y_columns")
        if not isinstance(y_columns, list) or not [c for c in y_columns if c]:
            raise ValueError(f"{self.type} requires at least one column in 'y_columns'.")
        if len(dict.fromkeys(y_columns)) > MAX_LINE_SERIES:
            raise ValueError(f"{self.type} supports at most {MAX_LINE_SERIES} series.")
        self._check_aggregate(config, "mean")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        x = config["x"]
        # De-duplicated, order-preserving: duplicate y picks would double-draw.
        y_columns = [c for c in dict.fromkeys(config.get("y_columns", [])) if c]
        aggregate = config.get("aggregate") or "mean"
        _require_columns(self.type, pdf, [x, *y_columns])

        sort_key = _x_sort_key(pdf, x)
        ordered = pdf.assign(**{"__chart_sort__": sort_key}).sort_values("__chart_sort__", kind="stable")
        labels = ordered[x].map(_label)

        # Cap the distinct x values BEFORE aggregating: a high-cardinality x
        # (ids, raw timestamps) would otherwise build millions of row dicts just
        # to throw most of them away.
        unique_labels = [str(v) for v in labels.drop_duplicates()]
        total_points = len(unique_labels)
        kept_labels = _stride_sample(unique_labels, MAX_LINE_POINTS)
        if total_points > MAX_LINE_POINTS:
            keep = labels.isin(set(kept_labels))
            ordered = ordered[keep]
            labels = labels[keep]

        # "x" is the reserved axis key on each row; a y column *named* "x" is
        # stored under an invisible-suffix key instead.
        key_for = {y: _safe_key(_short(y), frozenset({"x"})) for y in y_columns}
        rows: dict[str, dict[str, Any]] = {label: {"x": label} for label in kept_labels}
        for y in y_columns:
            if aggregate == "count":
                agg = ordered.groupby(labels, sort=False).size()
            else:
                agg = getattr(_numeric(ordered, y).groupby(labels, sort=False), aggregate)()
            for label, value in agg.items():
                rows[str(label)][key_for[y]] = _finite(value)

        return {
            "x": _short(x),
            "series": [key_for[y] for y in y_columns],
            "aggregate": aggregate,
            "rows": list(rows.values()),
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
        super().validate_config(config)
        if not config.get("x") or not config.get("y"):
            raise ValueError(f"{self.type} requires 'x' and 'y' columns.")
        if config.get("x") == config.get("y"):
            raise ValueError(f"{self.type} 'x' and 'y' must be different columns.")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        x, y = config["x"], config["y"]
        _require_columns(self.type, pdf, [x, y])
        xs = _numeric(pdf, x)
        ys = _numeric(pdf, y)
        mask = xs.notna() & ys.notna()
        pairs = [[_finite(a), _finite(b)] for a, b in zip(xs[mask], ys[mask], strict=True)]
        total_points = len(pairs)
        return {
            "x": _short(x),
            "y": _short(y),
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
        super().validate_config(config)
        if not config.get("category"):
            raise ValueError(f"{self.type} requires a 'category' column.")
        self._check_aggregate(config, "count")
        aggregate = config.get("aggregate") or "count"
        if aggregate != "count" and not config.get("value"):
            raise ValueError(f"{self.type} requires a 'value' column unless aggregate is 'count'.")
        _check_int(self.type, "limit", config.get("limit"), 2, MAX_PIE_SLICES)

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        category = config["category"]
        aggregate = config.get("aggregate") or "count"
        value = None if aggregate == "count" else (config.get("value") or None)
        limit = config.get("limit") or DEFAULT_PIE_SLICES
        _require_columns(self.type, pdf, [category, value or ""])
        data, total = _fold_other(pdf, category, value, aggregate, limit)
        return {
            "category": _short(category),
            "value": _short(value) if value else None,
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
        super().validate_config(config)
        if not config.get("column"):
            raise ValueError(f"{self.type} requires a 'column'.")
        _check_int(self.type, "bins", config.get("bins"), 1, MAX_HISTOGRAM_BINS)

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        column = config["column"]
        bins = config.get("bins") or DEFAULT_HISTOGRAM_BINS
        _require_columns(self.type, pdf, [column])
        values = _numeric(pdf, column).dropna()
        values = values[np.isfinite(values)]
        artifact: dict[str, Any] = {"column": _short(column), "bins": bins, "rows_seen": int(len(pdf))}
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
        super().validate_config(config)
        if not config.get("column"):
            raise ValueError(f"{self.type} requires a 'column'.")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        column = config["column"]
        group_by = config.get("group_by") or None
        _require_columns(self.type, pdf, [column, group_by or ""])

        if group_by:
            groups = pdf[group_by].map(_label)
        else:
            groups = pd.Series([_short(column)] * len(pdf), index=pdf.index)
        # ±inf would make every quantile/whisker non-finite (-> None) and break
        # the renderer's scale; treat it like missing data, as the histogram does.
        values = _numeric(pdf, column)
        values = values.where(np.isfinite(values))

        sizes = values.groupby(groups, sort=False).count().sort_values(ascending=False)
        sizes = sizes[sizes > 0]
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
            "column": _short(column),
            "group_by": _short(group_by) if group_by else None,
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
        super().validate_config(config)
        columns = config.get("columns")
        if columns is not None and not isinstance(columns, list):
            raise ValueError(f"{self.type} 'columns' must be a list of column names.")
        if isinstance(columns, list) and len([c for c in columns if c]) > MAX_HEATMAP_COLUMNS:
            raise ValueError(f"{self.type} supports at most {MAX_HEATMAP_COLUMNS} columns.")

    def _compute(self, pdf: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
        chosen = [c for c in dict.fromkeys(config.get("columns") or []) if c]
        if chosen:
            _require_columns(self.type, pdf, chosen)
            candidates = pdf[chosen]
        else:
            # Auto-selection considers real numbers and numeric-looking text, but
            # never datetimes — correlating nanosecond timestamps is meaningless.
            candidates = pdf.select_dtypes(exclude=["datetime", "datetimetz", "timedelta"])

        # Decide usability on a bounded sample so a wide text frame doesn't pay a
        # full-column string-parse per column; only the kept columns are coerced
        # in full below.
        sample = candidates.head(HEATMAP_DETECT_SAMPLE).apply(pd.to_numeric, errors="coerce")
        usable = [c for c in sample.columns if sample[c].notna().mean() >= 0.5 and sample[c].nunique() > 1]
        dropped = [str(c) for c in chosen if c not in usable]
        total_columns = len(usable)
        usable = usable[:MAX_HEATMAP_COLUMNS]

        artifact: dict[str, Any] = {
            "columns": [_short(str(c)) for c in usable],
            "matrix": [],
            "total_columns": total_columns,
            "dropped_columns": [_short(c) for c in dropped],
            "rows_seen": int(len(pdf)),
        }
        # Too few usable columns is a data-shape outcome, not a config mistake:
        # emit an empty artifact (the run view explains it) instead of failing a
        # whole run over a side-car visualization.
        if len(usable) < 2:
            artifact["columns"] = []
            return artifact
        numeric = pdf[usable].apply(pd.to_numeric, errors="coerce")
        corr = numeric.corr()
        artifact["matrix"] = [[_finite(corr.iloc[i, j]) for j in range(len(usable))] for i in range(len(usable))]
        return artifact
