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
            # Route through pandas+openpyxl to avoid an extra optional dep.
            return pl.from_pandas(pd.read_excel(path))
        raise ValueError(f"Unsupported source_type: {source_type!r}")

    def write(self, df: pl.DataFrame, path: str, source_type: str) -> None:
        if source_type == "csv":
            df.write_csv(path)
        elif source_type == "parquet":
            df.write_parquet(path)
        elif source_type == "excel":
            df.to_pandas().to_excel(path, index=False)
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
            case "isnull":
                expr = col.is_null()
            case "notnull":
                expr = col.is_not_null()
            case _:
                raise ValueError(f"Unknown filter operator: {operator!r}")
        return df.filter(expr)

    def fill_nulls(
        self, df: pl.DataFrame, columns: list[str] | None, value: Any
    ) -> pl.DataFrame:
        targets = columns or df.columns
        return df.with_columns(pl.col(targets).fill_null(value))

    def drop_nulls(self, df: pl.DataFrame, columns: list[str] | None) -> pl.DataFrame:
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

    def cast_column(self, df: pl.DataFrame, column: str, dtype: str) -> pl.DataFrame:
        if dtype == "datetime":
            return df.with_columns(
                pl.col(column).str.to_datetime(strict=False)
                if df.schema[column] == pl.Utf8
                else pl.col(column).cast(pl.Datetime)
            )
        if dtype not in _DTYPE_MAP:
            raise ValueError(f"Unknown dtype: {dtype!r}")
        return df.with_columns(pl.col(column).cast(_DTYPE_MAP[dtype]))

    def sort_rows(
        self, df: pl.DataFrame, columns: list[str], ascending: list[bool]
    ) -> pl.DataFrame:
        descending = [not a for a in ascending]
        return df.sort(by=columns, descending=descending)

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
        self, left: pl.DataFrame, right: pl.DataFrame, on: list[str], how: str
    ) -> pl.DataFrame:
        if how not in _JOIN_HOW:
            raise ValueError(f"Unsupported join how: {how!r}")
        return left.join(right, on=on, how=_JOIN_HOW[how])  # type: ignore[arg-type]

    def concat(self, frames: list[pl.DataFrame]) -> pl.DataFrame:
        return pl.concat(frames, how="vertical_relaxed")

    def limit_rows(self, df: pl.DataFrame, n: int) -> pl.DataFrame:
        return df.head(n)

    def replace_values(
        self, df: pl.DataFrame, column: str, to_replace: Any, value: Any
    ) -> pl.DataFrame:
        return df.with_columns(pl.col(column).replace(to_replace, value))

    def string_transform(
        self, df: pl.DataFrame, column: str, operation: str
    ) -> pl.DataFrame:
        col = pl.col(column).cast(pl.Utf8).str
        ops = {
            "lower": col.to_lowercase,
            "upper": col.to_uppercase,
            "strip": col.strip_chars,
            "title": col.to_titlecase,
            "capitalize": col.to_titlecase,
        }
        if operation not in ops:
            raise ValueError(f"Unknown string operation: {operation!r}")
        return df.with_columns(ops[operation]().alias(column))
