from __future__ import annotations

from typing import Any, Literal, cast

import pandas as pd
import polars as pl

from app.engine.backends.base import register_engine

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
_AGG_FUNCS = {
    "sum",
    "mean",
    "min",
    "max",
    "count",
    "median",
    "std",
    "first",
    "last",
    "n_unique",
}


@register_engine
class PolarsEngine:
    name = "polars"

    # -- I/O ------------------------------------------------------------

    def read(self, path: str, source_type: str) -> pl.DataFrame:
        if source_type == "csv":
            return pl.read_csv(path)
        if source_type == "parquet":
            return pl.read_parquet(path)
        if source_type == "excel":
            # Native polars read (via openpyxl, already a dependency) so Excel gets
            # the same type inference as the CSV/Parquet paths — not pandas'.
            return pl.read_excel(path, engine="openpyxl")
        raise ValueError(f"Unsupported source_type: {source_type!r}")

    def write(self, df: pl.DataFrame, path: str, source_type: str) -> None:
        if source_type == "csv":
            df.write_csv(path)
        elif source_type == "parquet":
            df.write_parquet(path)
        elif source_type == "excel":
            df.write_excel(path)
        else:
            raise ValueError(f"Unsupported source_type: {source_type!r}")

    def to_pandas(self, df: pl.DataFrame) -> pd.DataFrame:
        return df.to_pandas()

    def to_records(self, df: pl.DataFrame, n: int | None = None) -> list[dict[str, Any]]:
        sample = df.head(n) if n is not None else df
        return sample.to_dicts()

    def row_count(self, df: pl.DataFrame) -> int:
        return df.height

    # -- Operations -----------------------------------------------------

    def rename_columns(self, df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
        return df.rename(mapping)

    def drop_columns(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        return df.drop(columns)

    def filter_rows(
        self, df: pl.DataFrame, column: str, operator: str, value: Any
    ) -> pl.DataFrame:
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

    def fill_nulls(
        self, df: pl.DataFrame, columns: list[str] | None, strategy: str, value: Any
    ) -> pl.DataFrame:
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
                exprs.append(
                    col.fill_null(strategy=cast(Any, self._FILL_STRATEGY[strategy]))
                )
            elif strategy == "median":
                exprs.append(col.fill_null(df[col_name].median()))
            elif strategy == "mode":
                modes = df[col_name].drop_nulls().mode()
                exprs.append(col.fill_null(modes[0]) if len(modes) else col)
            else:
                raise ValueError(f"Unknown fill strategy: {strategy!r}")
        return df.with_columns(exprs)

    def drop_nulls(
        self, df: pl.DataFrame, columns: list[str] | None, how: str = "any"
    ) -> pl.DataFrame:
        if how == "all":
            cols = columns or df.columns
            return df.filter(~pl.all_horizontal([pl.col(c).is_null() for c in cols]))
        return df.drop_nulls(subset=columns or None)

    def drop_duplicates(
        self, df: pl.DataFrame, subset: list[str] | None, keep: str | bool = "first"
    ) -> pl.DataFrame:
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

    def groupby_agg(
        self, df: pl.DataFrame, by: list[str], aggregations: dict[str, str]
    ) -> pl.DataFrame:
        exprs = []
        for column, func in aggregations.items():
            if func not in _AGG_FUNCS:
                raise ValueError(f"Unsupported aggregation function: {func!r}")
            exprs.append(getattr(pl.col(column), func)().alias(column))
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
            return left.join(
                right, left_on=left_on, right_on=right_on, how=how_arg, suffix=suffix
            )
        return left.join(right, on=on, how=how_arg, suffix=suffix)

    def concat(self, frames: list[pl.DataFrame]) -> pl.DataFrame:
        return pl.concat(frames, how="vertical_relaxed")

    def limit_rows(self, df: pl.DataFrame, n: int, offset: int = 0) -> pl.DataFrame:
        return df.slice(offset, n)

    def replace_values(
        self, df: pl.DataFrame, column: str, to_replace: Any, value: Any, regex: bool = False
    ) -> pl.DataFrame:
        if regex:
            return df.with_columns(
                pl.col(column).cast(pl.Utf8).str.replace_all(str(to_replace), str(value))
            )
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
        elif operation in ("title", "capitalize"):
            expr = s.to_titlecase()
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

    def sample_rows(
        self, df: pl.DataFrame, n: int | None, frac: float | None, seed: int | None
    ) -> pl.DataFrame:
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
            return cast(float, series.quantile(lower / 100)), cast(
                float, series.quantile(upper / 100)
            )
        raise ValueError(f"Unknown outlier method: {method!r}")

    def round_columns(
        self, df: pl.DataFrame, columns: list[str], decimals: int
    ) -> pl.DataFrame:
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

    def extract_date_parts(
        self, df: pl.DataFrame, column: str, parts: list[str]
    ) -> pl.DataFrame:
        dt = (
            pl.col(column).str.to_datetime(strict=False)
            if df.schema[column] == pl.Utf8
            else pl.col(column).cast(pl.Datetime, strict=False)
        )
        accessors = {
            "year": dt.dt.year(),
            "month": dt.dt.month(),
            "day": dt.dt.day(),
            "weekday": dt.dt.weekday(),
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
        return df.pivot(
            on=columns, index=index, values=values, aggregate_function=cast(Any, agg)
        )
