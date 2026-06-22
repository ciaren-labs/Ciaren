from __future__ import annotations

import json
from typing import Any, Literal, cast

import pandas as pd

from .base import register_engine


@register_engine
class PandasEngine:
    name = "pandas"

    # -- I/O ------------------------------------------------------------

    def read(self, path: str, source_type: str) -> pd.DataFrame:
        if source_type == "csv":
            return pd.read_csv(path)
        if source_type == "excel":
            return pd.read_excel(path)
        if source_type == "parquet":
            return pd.read_parquet(path)
        raise ValueError(f"Unsupported source_type: {source_type!r}")

    def write(self, df: pd.DataFrame, path: str, source_type: str) -> None:
        if source_type == "csv":
            df.to_csv(path, index=False)
        elif source_type == "excel":
            df.to_excel(path, index=False)
        elif source_type == "parquet":
            df.to_parquet(path, index=False)
        else:
            raise ValueError(f"Unsupported source_type: {source_type!r}")

    def to_pandas(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def to_records(self, df: pd.DataFrame, n: int | None = None) -> list[dict[str, Any]]:
        sample = df.head(n) if n is not None else df
        records = json.loads(sample.to_json(orient="records", date_format="iso"))
        return cast(list[dict[str, Any]], records)

    def row_count(self, df: pd.DataFrame) -> int:
        return len(df)

    # -- Operations -----------------------------------------------------

    def rename_columns(self, df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
        return df.rename(columns=mapping)

    def drop_columns(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        return df.drop(columns=columns)

    def filter_rows(
        self, df: pd.DataFrame, column: str, operator: str, value: Any
    ) -> pd.DataFrame:
        col = df[column]
        match operator:
            case "==" | "eq":
                mask = col == value
            case "!=" | "ne":
                mask = col != value
            case ">" | "gt":
                mask = col > value
            case ">=" | "gte":
                mask = col >= value
            case "<" | "lt":
                mask = col < value
            case "<=" | "lte":
                mask = col <= value
            case "contains":
                mask = col.astype(str).str.contains(str(value), na=False)
            case "startswith":
                mask = col.astype(str).str.startswith(str(value), na=False)
            case "endswith":
                mask = col.astype(str).str.endswith(str(value), na=False)
            case "isnull":
                mask = col.isna()
            case "notnull":
                mask = col.notna()
            case _:
                raise ValueError(f"Unknown filter operator: {operator!r}")
        filtered: pd.DataFrame = df[mask]
        return filtered

    def fill_nulls(
        self, df: pd.DataFrame, columns: list[str] | None, value: Any
    ) -> pd.DataFrame:
        targets = columns or df.columns.tolist()
        result = df.copy()
        for col in targets:
            original_dtype = df[col].dtype
            try:
                typed_value = pd.array([value], dtype=original_dtype)[0]
            except (ValueError, TypeError):
                continue
            result[col] = df[col].fillna(typed_value)
        return result

    def drop_nulls(
        self, df: pd.DataFrame, columns: list[str] | None
    ) -> pd.DataFrame:
        result: pd.DataFrame = df.dropna(subset=columns or None)
        return result

    def drop_duplicates(
        self, df: pd.DataFrame, subset: list[str] | None, keep: str | bool = "first"
    ) -> pd.DataFrame:
        keep_arg = cast(Literal["first", "last", False], keep)
        result: pd.DataFrame = df.drop_duplicates(subset=subset or None, keep=keep_arg)
        return result

    def cast_column(self, df: pd.DataFrame, column: str, dtype: str) -> pd.DataFrame:
        _DTYPE_MAP = {
            "integer": "Int64",
            "float": "float64",
            "boolean": "boolean",
            "string": "string",
        }
        if dtype == "datetime":
            return df.assign(**{column: pd.to_datetime(df[column])})
        if dtype not in _DTYPE_MAP:
            raise ValueError(f"Unknown dtype: {dtype!r}")
        return df.assign(**{column: df[column].astype(cast(Any, _DTYPE_MAP[dtype]))})

    def sort_rows(
        self, df: pd.DataFrame, columns: list[str], ascending: list[bool]
    ) -> pd.DataFrame:
        return df.sort_values(by=columns, ascending=ascending)

    def select_columns(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        return df[columns]

    def add_column(self, df: pd.DataFrame, name: str, expression: str) -> pd.DataFrame:
        return df.assign(**{name: cast(Any, df.eval(expression))})

    def groupby_agg(
        self, df: pd.DataFrame, by: list[str], aggregations: dict[str, str]
    ) -> pd.DataFrame:
        return df.groupby(by).agg(aggregations).reset_index()

    def join(
        self, left: pd.DataFrame, right: pd.DataFrame, on: list[str], how: str
    ) -> pd.DataFrame:
        how_arg = cast(Literal["left", "right", "outer", "inner", "cross"], how)
        return left.merge(right, on=on, how=how_arg)

    def concat(self, frames: list[pd.DataFrame]) -> pd.DataFrame:
        return pd.concat(frames, ignore_index=True)

    def limit_rows(self, df: pd.DataFrame, n: int) -> pd.DataFrame:
        return df.head(n)

    def replace_values(
        self, df: pd.DataFrame, column: str, to_replace: Any, value: Any
    ) -> pd.DataFrame:
        return df.assign(**{column: df[column].replace(to_replace, value)})

    def string_transform(
        self, df: pd.DataFrame, column: str, operation: str
    ) -> pd.DataFrame:
        accessor = df[column].astype("string").str
        ops = {
            "lower": accessor.lower,
            "upper": accessor.upper,
            "strip": accessor.strip,
            "title": accessor.title,
            "capitalize": accessor.capitalize,
        }
        if operation not in ops:
            raise ValueError(f"Unknown string operation: {operation!r}")
        return df.assign(**{column: ops[operation]()})
