from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any, Literal, cast

import pandas as pd
import polars as pl

from app.engine.backends.base import register_engine, rule_combine_all, rule_conditions


def _json_safe(v: Any) -> Any:
    """Coerce a polars cell value into a JSON-serializable primitive.

    polars ``to_dicts`` yields native ``datetime``/``date``/``Decimal`` objects;
    these records are persisted to a JSON column and returned over the API, so
    temporal values become ISO strings (matching the pandas backend), durations
    become seconds, and Decimals become floats. Nested lists/structs recurse.
    """
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
        return v.isoformat()
    if isinstance(v, _dt.timedelta):
        return v.total_seconds()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    return v


# How values accepted by the public API mapped to polars' own vocabulary.
_JOIN_HOW = {
    "inner": "inner",
    "left": "left",
    "right": "right",
    "outer": "full",
}

_DTYPE_MAP = {
    "integer": pl.Int64,
    "float": pl.Float64,
    "boolean": pl.Boolean,
    "string": pl.Utf8,
}

# Aggregation function name -> method invoked on a pl.col(...) expression.
# User-facing aggregation name -> polars Expr method. pandas-style names
# (e.g. "nunique") are accepted and translated so both engines take the same
# config. Names that map to themselves are still listed for validation.
_AGG_FUNCS = {
    "sum": "sum",
    "mean": "mean",
    "min": "min",
    "max": "max",
    "count": "count",
    "median": "median",
    "std": "std",
    "first": "first",
    "last": "last",
    "nunique": "n_unique",
    "n_unique": "n_unique",
}


@register_engine
class PolarsEngine:
    name = "polars"

    # -- I/O ------------------------------------------------------------

    def read(self, path: str, source_type: str) -> pl.DataFrame:
        if source_type == "csv":
            # Lazy scan + streaming collect reads the file in batches, so the peak
            # memory needed to load a large CSV is a fraction of read_csv's. The
            # result is byte-identical to read_csv (same parser/inference).
            return pl.scan_csv(path).collect(engine="streaming")
        if source_type == "tsv":
            return pl.scan_csv(path, separator="\t").collect(engine="streaming")
        if source_type == "parquet":
            return pl.scan_parquet(path).collect(engine="streaming")
        if source_type == "excel":
            # Native polars read (via openpyxl, already a dependency) so Excel gets
            # the same type inference as the CSV/Parquet paths — not pandas'.
            return pl.read_excel(path, engine="openpyxl")
        if source_type == "json":
            return pl.read_json(path)
        if source_type == "jsonl":
            return pl.read_ndjson(path)
        if source_type == "text":
            # One row per line. splitlines() is robust — newer pandas rejects sep="\n".
            from pathlib import Path

            return pl.DataFrame({"text": Path(path).read_text(encoding="utf-8").splitlines()})
        raise ValueError(f"Unsupported source_type: {source_type!r}")

    def write(self, df: pl.DataFrame, path: str, source_type: str) -> None:
        if source_type == "csv":
            df.write_csv(path)
        elif source_type == "tsv":
            df.write_csv(path, separator="\t")
        elif source_type == "parquet":
            df.write_parquet(path)
        elif source_type == "excel":
            df.write_excel(path)
        elif source_type == "json":
            df.write_json(path)
        elif source_type == "jsonl":
            df.write_ndjson(path)
        elif source_type == "text":
            # One row per line; tab-separated for wider frames (mirrors text input).
            df.write_csv(path, include_header=False, separator="\t")
        else:
            raise ValueError(f"Unsupported source_type: {source_type!r}")

    def to_pandas(self, df: pl.DataFrame) -> pd.DataFrame:
        return df.to_pandas()

    def from_pandas(self, df: pd.DataFrame) -> pl.DataFrame:
        # Arrow-backed conversion (~zero-copy for numeric columns).
        return pl.from_pandas(df)

    def to_records(self, df: pl.DataFrame, n: int | None = None) -> list[dict[str, Any]]:
        sample = df.head(n) if n is not None else df
        # to_dicts() returns native datetime/date/Decimal objects, which are not
        # JSON-serializable — these records are stored in a JSON column (run
        # node_results) and returned over the API. Coerce to JSON-safe primitives,
        # matching the pandas backend (ISO date strings).
        return [{k: _json_safe(v) for k, v in row.items()} for row in sample.to_dicts()]

    def row_count(self, df: pl.DataFrame) -> int:
        return df.height

    def column_names(self, df: pl.DataFrame) -> list[str]:
        return df.columns

    # -- Operations -----------------------------------------------------

    def rename_columns(self, df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
        return df.rename(mapping)

    def drop_columns(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        return df.drop(columns)

    def filter_rows(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        col = pl.col(column)
        match operator:
            case "==" | "eq":
                expr = col == value
            case "!=" | "ne":
                expr = col != value
            case ">" | "gt":
                expr = col > value
            case ">=" | "gte":
                expr = col >= value
            case "<" | "lt":
                expr = col < value
            case "<=" | "lte":
                expr = col <= value
            case "contains":
                expr = col.cast(pl.Utf8).str.contains(str(value), literal=True)
            case "startswith":
                expr = col.cast(pl.Utf8).str.starts_with(str(value))
            case "endswith":
                expr = col.cast(pl.Utf8).str.ends_with(str(value))
            case "between":
                low, high = value
                expr = col.is_between(low, high)
            case "in":
                expr = col.is_in(list(value))
            case "isnull":
                expr = col.is_null()
            case "notnull":
                expr = col.is_not_null()
            case _:
                raise ValueError(f"Unknown filter operator: {operator!r}")
        return df.filter(expr)

    # Strategies polars' fill_null accepts directly (rest are computed manually).
    _FILL_STRATEGY = {
        "mean": "mean",
        "min": "min",
        "max": "max",
        "zero": "zero",
        "ffill": "forward",
        "bfill": "backward",
    }

    def fill_nulls(self, df: pl.DataFrame, columns: list[str] | None, strategy: str, value: Any) -> pl.DataFrame:
        targets = columns or df.columns
        exprs = []
        for col_name in targets:
            col = pl.col(col_name)
            if strategy == "constant":
                col_dtype = df[col_name].dtype
                try:
                    typed_value = pl.Series("_", [value]).cast(col_dtype)[0]
                    exprs.append(col.fill_null(typed_value))
                except Exception:
                    exprs.append(col)
            elif strategy in self._FILL_STRATEGY:
                exprs.append(col.fill_null(strategy=cast(Any, self._FILL_STRATEGY[strategy])))
            elif strategy == "median":
                exprs.append(col.fill_null(df[col_name].median()))
            elif strategy == "mode":
                modes = df[col_name].drop_nulls().mode()
                exprs.append(col.fill_null(modes[0]) if len(modes) else col)
            else:
                raise ValueError(f"Unknown fill strategy: {strategy!r}")
        return df.with_columns(exprs)

    def drop_nulls(self, df: pl.DataFrame, columns: list[str] | None, how: str = "any") -> pl.DataFrame:
        if how == "all":
            cols = columns or df.columns
            return df.filter(~pl.all_horizontal([pl.col(c).is_null() for c in cols]))
        return df.drop_nulls(subset=columns or None)

    def drop_duplicates(self, df: pl.DataFrame, subset: list[str] | None, keep: str | bool = "first") -> pl.DataFrame:
        # pandas allows keep=False (drop all dups); polars uses keep="none".
        polars_keep = cast(
            Literal["first", "last", "any", "none"],
            "none" if keep is False else keep,
        )
        return df.unique(subset=subset or None, keep=polars_keep, maintain_order=True)

    def cast_column(
        self,
        df: pl.DataFrame,
        column: str,
        dtype: str,
        fmt: str | None = None,
        errors: str = "raise",
    ) -> pl.DataFrame:
        strict = errors != "coerce"
        if dtype == "datetime":
            return df.with_columns(
                pl.col(column).str.to_datetime(format=fmt, strict=strict)
                if df.schema[column] == pl.Utf8
                else pl.col(column).cast(pl.Datetime, strict=strict)
            )
        if dtype not in _DTYPE_MAP:
            raise ValueError(f"Unknown dtype: {dtype!r}")
        return df.with_columns(pl.col(column).cast(_DTYPE_MAP[dtype], strict=strict))

    def sort_rows(
        self,
        df: pl.DataFrame,
        columns: list[str],
        ascending: list[bool],
        na_position: str = "last",
    ) -> pl.DataFrame:
        descending = [not a for a in ascending]
        return df.sort(by=columns, descending=descending, nulls_last=na_position == "last")

    def select_columns(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        return df.select(columns)

    def add_column(self, df: pl.DataFrame, name: str, expression: str) -> pl.DataFrame:
        # SQL expression parsing handles arithmetic like "price * quantity".
        return df.with_columns(pl.sql_expr(expression).alias(name))

    def groupby_agg(self, df: pl.DataFrame, by: list[str], aggregations: dict[str, str]) -> pl.DataFrame:
        exprs = []
        for column, func in aggregations.items():
            if func not in _AGG_FUNCS:
                raise ValueError(f"Unsupported aggregation function: {func!r}")
            method = _AGG_FUNCS[func]
            exprs.append(getattr(pl.col(column), method)().alias(column))
        return df.group_by(by, maintain_order=True).agg(exprs)

    def join(
        self,
        left: pl.DataFrame,
        right: pl.DataFrame,
        on: list[str] | None,
        how: str,
        left_on: list[str] | None = None,
        right_on: list[str] | None = None,
        suffixes: tuple[str, str] = ("_x", "_y"),
    ) -> pl.DataFrame:
        if how not in _JOIN_HOW:
            raise ValueError(f"Unsupported join how: {how!r}")
        how_arg = cast(Any, _JOIN_HOW[how])
        # polars takes a single suffix for overlapping right-side columns.
        suffix = suffixes[1]
        if left_on and right_on:
            return left.join(right, left_on=left_on, right_on=right_on, how=how_arg, suffix=suffix)
        # coalesce shared keys so a 'full'/'outer' join keeps a single key column,
        # matching pandas.merge(on=...). (Without it polars emits a duplicate 'key_y'.)
        return left.join(right, on=on, how=how_arg, suffix=suffix, coalesce=True)

    def concat(self, frames: list[pl.DataFrame]) -> pl.DataFrame:
        return pl.concat(frames, how="vertical_relaxed")

    def limit_rows(self, df: pl.DataFrame, n: int, offset: int = 0) -> pl.DataFrame:
        return df.slice(offset, n)

    def replace_values(
        self, df: pl.DataFrame, column: str, to_replace: Any, value: Any, regex: bool = False
    ) -> pl.DataFrame:
        if regex:
            return df.with_columns(pl.col(column).cast(pl.Utf8).str.replace_all(str(to_replace), str(value)))
        return df.with_columns(pl.col(column).replace(to_replace, value))

    def string_transform(
        self,
        df: pl.DataFrame,
        column: str,
        operation: str,
        find: str | None = None,
        replace_with: str | None = None,
        width: int | None = None,
        fill_char: str = " ",
        side: str = "left",
    ) -> pl.DataFrame:
        s = pl.col(column).cast(pl.Utf8).str
        expr: pl.Expr
        if operation == "lower":
            expr = s.to_lowercase()
        elif operation == "upper":
            expr = s.to_uppercase()
        elif operation == "strip":
            expr = s.strip_chars()
        elif operation == "title":
            expr = s.to_titlecase()
        elif operation == "capitalize":
            # pandas capitalize: first char upper, the rest lower (whole string).
            expr = s.slice(0, 1).str.to_uppercase() + s.slice(1).str.to_lowercase()
        elif operation == "len":
            expr = s.len_chars()
        elif operation == "replace":
            expr = s.replace_all(str(find), str(replace_with), literal=True)
        elif operation == "pad":
            w = cast(int, width)
            expr = s.pad_end(w, fill_char) if side == "right" else s.pad_start(w, fill_char)
        else:
            raise ValueError(f"Unknown string operation: {operation!r}")
        return df.with_columns(expr.alias(column))

    # -- New nodes (Phase 3) -------------------------------------------

    def sample_rows(self, df: pl.DataFrame, n: int | None, frac: float | None, seed: int | None) -> pl.DataFrame:
        if frac is not None:
            return df.sample(fraction=frac, seed=seed)
        return df.sample(n=cast(int, n), seed=seed)

    def remove_outliers(
        self,
        df: pl.DataFrame,
        columns: list[str],
        method: str,
        action: str,
        factor: float,
        threshold: float,
        lower: float,
        upper: float,
    ) -> pl.DataFrame:
        clip_exprs: list[pl.Expr] = []
        keep = pl.lit(True)
        for col in columns:
            series = df[col]
            lo, hi = self._outlier_bounds(series, method, factor, threshold, lower, upper)
            if action == "clip":
                clip_exprs.append(pl.col(col).clip(lo, hi))
            else:
                keep = keep & (pl.col(col).is_between(lo, hi) | pl.col(col).is_null())
        return df.with_columns(clip_exprs) if action == "clip" else df.filter(keep)

    @staticmethod
    def _outlier_bounds(
        series: pl.Series,
        method: str,
        factor: float,
        threshold: float,
        lower: float,
        upper: float,
    ) -> tuple[float, float]:
        if method == "iqr":
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = cast(float, q3) - cast(float, q1)
            return cast(float, q1) - factor * iqr, cast(float, q3) + factor * iqr
        if method == "zscore":
            mean, std = cast(float, series.mean()), cast(float, series.std())
            return mean - threshold * std, mean + threshold * std
        if method == "percentile":
            return cast(float, series.quantile(lower / 100)), cast(float, series.quantile(upper / 100))
        raise ValueError(f"Unknown outlier method: {method!r}")

    def round_columns(self, df: pl.DataFrame, columns: list[str], decimals: int) -> pl.DataFrame:
        return df.with_columns([pl.col(c).round(decimals) for c in columns])

    def bin_column(
        self,
        df: pl.DataFrame,
        column: str,
        new_column: str,
        method: str,
        bins: int,
        labels: list[str] | None,
    ) -> pl.DataFrame:
        if method == "quantile":
            quantiles = [i / bins for i in range(1, bins)]
            expr = pl.col(column).qcut(quantiles, labels=labels, allow_duplicates=True)
        else:
            lo = cast(float, df[column].min())
            hi = cast(float, df[column].max())
            step = (hi - lo) / bins
            breaks = [lo + step * i for i in range(1, bins)]
            expr = pl.col(column).cut(breaks, labels=labels)
        return df.with_columns(expr.cast(pl.Utf8).alias(new_column))

    def extract_date_parts(self, df: pl.DataFrame, column: str, parts: list[str]) -> pl.DataFrame:
        dt = (
            pl.col(column).str.to_datetime(strict=False)
            if df.schema[column] == pl.Utf8
            else pl.col(column).cast(pl.Datetime, strict=False)
        )
        accessors = {
            "year": dt.dt.year(),
            "month": dt.dt.month(),
            "day": dt.dt.day(),
            # polars weekday is Monday=1..Sunday=7; pandas is Monday=0..Sunday=6.
            "weekday": dt.dt.weekday() - 1,
            "hour": dt.dt.hour(),
        }
        return df.with_columns([accessors[p].alias(f"{column}_{p}") for p in parts])

    def unpivot(
        self,
        df: pl.DataFrame,
        id_vars: list[str],
        value_vars: list[str] | None,
        var_name: str,
        value_name: str,
    ) -> pl.DataFrame:
        return df.unpivot(
            index=id_vars or None,
            on=value_vars or None,
            variable_name=var_name,
            value_name=value_name,
        )

    def pivot(
        self,
        df: pl.DataFrame,
        index: list[str],
        columns: str,
        values: str,
        aggfunc: str,
    ) -> pl.DataFrame:
        agg = "len" if aggfunc == "count" else aggfunc
        return df.pivot(on=columns, index=index, values=values, aggregate_function=cast(Any, agg))

    # -- New nodes (text/date/value mapping) ---------------------------

    def split_column(
        self,
        df: pl.DataFrame,
        column: str,
        into: list[str],
        mode: str,
        delimiter: str,
        pattern: str,
        keep_original: bool,
    ) -> pl.DataFrame:
        src = pl.col(column).cast(pl.Utf8)
        if mode == "regex":
            exprs = [src.str.extract(pattern, i + 1).alias(name) for i, name in enumerate(into)]
        else:
            split = src.str.split(delimiter)
            exprs = [split.list.get(i, null_on_oob=True).alias(name) for i, name in enumerate(into)]
        result = df.with_columns(exprs)
        if not keep_original and column not in into:
            result = result.drop(column)
        return result

    def parse_dates(self, df: pl.DataFrame, columns: list[str], fmt: str | None, errors: str) -> pl.DataFrame:
        strict = errors != "coerce"
        exprs = []
        for c in columns:
            col = pl.col(c)
            expr = (
                col.str.to_datetime(format=fmt, strict=strict)
                if df.schema[c] == pl.Utf8
                else col.cast(pl.Datetime, strict=strict)
            )
            exprs.append(expr.alias(c))
        return df.with_columns(exprs)

    def map_values(
        self,
        df: pl.DataFrame,
        column: str,
        new_column: str | None,
        mapping: dict[Any, Any],
        default: Any,
        use_default: bool,
    ) -> pl.DataFrame:
        target = new_column or column
        col = pl.col(column)
        # replace_strict + default maps unmapped values to the default; plain
        # replace (no default) keeps unmapped values unchanged.
        expr = col.replace_strict(mapping, default=default) if use_default else col.replace(mapping)
        return df.with_columns(expr.alias(target))

    def window_function(
        self,
        df: pl.DataFrame,
        function: str,
        partition_by: list[str],
        order_by: list[str],
        target: str | None,
        offset: int,
        descending: bool,
        new_column: str,
    ) -> pl.DataFrame:
        # Tag original order, sort by the window order, compute, then restore.
        work = df.with_row_index("__rn__")
        if order_by:
            work = work.sort(by=order_by, descending=descending)
        expr = _polars_window_expr(function, partition_by or None, order_by, target, offset, descending)
        work = work.with_columns(expr.alias(new_column))
        return work.sort("__rn__").drop("__rn__")

    def conditional_column(
        self,
        df: pl.DataFrame,
        rules: list[dict[str, Any]],
        default: Any,
        new_column: str,
    ) -> pl.DataFrame:
        chain: Any = None
        for rule in rules:
            cond = _polars_rule_expr(rule)
            result = pl.lit(rule.get("result"))
            chain = pl.when(cond).then(result) if chain is None else chain.when(cond).then(result)
        expr = pl.lit(default) if chain is None else chain.otherwise(pl.lit(default))
        return df.with_columns(expr.alias(new_column))


def _polars_window_expr(
    function: str,
    part: list[str] | None,
    order_by: list[str],
    target: str | None,
    offset: int,
    descending: bool,
) -> pl.Expr:
    """Build the windowed expression (caller has already sorted by ``order_by``)."""
    if function == "row_number":
        expr = pl.int_range(1, pl.len() + 1)
    elif function == "cumcount":
        expr = pl.int_range(0, pl.len())
    elif function in ("rank", "dense_rank"):
        method = "dense" if function == "dense_rank" else "min"
        expr = pl.col(order_by[0]).rank(method=cast(Any, method), descending=descending)
    elif function in ("cumsum", "cummax", "cummin"):
        method = {"cumsum": "cum_sum", "cummax": "cum_max", "cummin": "cum_min"}[function]
        expr = getattr(pl.col(cast(str, target)), method)()
    elif function in ("lag", "lead"):
        expr = pl.col(cast(str, target)).shift(offset if function == "lag" else -offset)
    else:
        raise ValueError(f"Unknown window function: {function!r}")
    return expr.over(part) if part else expr


def _polars_rule_expr(rule: dict[str, Any]) -> pl.Expr:
    """Combine a rule's conditions with AND (match all) or OR (match any)."""
    exprs = [
        _polars_condition_expr(c["column"], c.get("operator", "=="), c.get("value")) for c in rule_conditions(rule)
    ]
    combined = exprs[0]
    combine_all = rule_combine_all(rule)
    for expr in exprs[1:]:
        combined = combined & expr if combine_all else combined | expr
    return combined


def _polars_condition_expr(column: str, operator: str, value: Any) -> pl.Expr:
    """Boolean expression for one conditionalColumn condition (mirrors filter operators)."""
    col = pl.col(column)
    expr: Any
    match operator:
        case "==" | "eq":
            expr = col == value
        case "!=" | "ne":
            expr = col != value
        case ">" | "gt":
            expr = col > value
        case ">=" | "gte":
            expr = col >= value
        case "<" | "lt":
            expr = col < value
        case "<=" | "lte":
            expr = col <= value
        case "contains":
            expr = col.cast(pl.Utf8).str.contains(str(value), literal=True)
        case "startswith":
            expr = col.cast(pl.Utf8).str.starts_with(str(value))
        case "endswith":
            expr = col.cast(pl.Utf8).str.ends_with(str(value))
        case "isnull":
            expr = col.is_null()
        case "notnull":
            expr = col.is_not_null()
        case _:
            raise ValueError(f"Unknown condition operator: {operator!r}")
    return cast(pl.Expr, expr)
