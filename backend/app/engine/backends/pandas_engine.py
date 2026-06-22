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
            case "between":
                low, high = value
                mask = col.between(low, high)
            case "in":
                mask = col.isin(list(value))
            case "isnull":
                mask = col.isna()
            case "notnull":
                mask = col.notna()
            case _:
                raise ValueError(f"Unknown filter operator: {operator!r}")
        filtered: pd.DataFrame = df[mask]
        return filtered

    def fill_nulls(
        self, df: pd.DataFrame, columns: list[str] | None, strategy: str, value: Any
    ) -> pd.DataFrame:
        targets = columns or df.columns.tolist()
        result = df.copy()
        for col in targets:
            series = df[col]
            if strategy == "constant":
                try:
                    fill: Any = pd.array([value], dtype=cast(Any, series.dtype))[0]
                except (ValueError, TypeError):
                    continue
            elif strategy == "zero":
                fill = 0
            elif strategy == "mean":
                if not pd.api.types.is_numeric_dtype(series):
                    continue
                fill = series.mean()
            elif strategy == "median":
                if not pd.api.types.is_numeric_dtype(series):
                    continue
                fill = series.median()
            elif strategy == "min":
                fill = series.min()
            elif strategy == "max":
                fill = series.max()
            elif strategy == "mode":
                modes = series.mode(dropna=True)
                if modes.empty:
                    continue
                fill = modes.iloc[0]
            elif strategy == "ffill":
                result[col] = series.ffill()
                continue
            elif strategy == "bfill":
                result[col] = series.bfill()
                continue
            else:
                raise ValueError(f"Unknown fill strategy: {strategy!r}")
            result[col] = series.fillna(fill)
        return result

    def drop_nulls(
        self, df: pd.DataFrame, columns: list[str] | None, how: str = "any"
    ) -> pd.DataFrame:
        how_arg = cast(Literal["any", "all"], how)
        result: pd.DataFrame = df.dropna(subset=columns or None, how=how_arg)
        return result

    def drop_duplicates(
        self, df: pd.DataFrame, subset: list[str] | None, keep: str | bool = "first"
    ) -> pd.DataFrame:
        keep_arg = cast(Literal["first", "last", False], keep)
        result: pd.DataFrame = df.drop_duplicates(subset=subset or None, keep=keep_arg)
        return result

    def cast_column(
        self,
        df: pd.DataFrame,
        column: str,
        dtype: str,
        fmt: str | None = None,
        errors: str = "raise",
    ) -> pd.DataFrame:
        _DTYPE_MAP = {
            "integer": "Int64",
            "float": "float64",
            "boolean": "boolean",
            "string": "string",
        }
        err: Literal["raise", "coerce"] = "coerce" if errors == "coerce" else "raise"
        if dtype == "datetime":
            return df.assign(
                **{column: pd.to_datetime(df[column], format=fmt or None, errors=err)}
            )
        if dtype not in _DTYPE_MAP:
            raise ValueError(f"Unknown dtype: {dtype!r}")
        if dtype in ("integer", "float") and errors == "coerce":
            numeric = pd.to_numeric(df[column], errors="coerce")
            return df.assign(**{column: numeric.astype(cast(Any, _DTYPE_MAP[dtype]))})
        return df.assign(**{column: df[column].astype(cast(Any, _DTYPE_MAP[dtype]))})

    def sort_rows(
        self,
        df: pd.DataFrame,
        columns: list[str],
        ascending: list[bool],
        na_position: str = "last",
    ) -> pd.DataFrame:
        pos = cast(Literal["first", "last"], na_position)
        return df.sort_values(by=columns, ascending=ascending, na_position=pos)

    def select_columns(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        return df[columns]

    def add_column(self, df: pd.DataFrame, name: str, expression: str) -> pd.DataFrame:
        return df.assign(**{name: cast(Any, df.eval(expression))})

    def groupby_agg(
        self, df: pd.DataFrame, by: list[str], aggregations: dict[str, str]
    ) -> pd.DataFrame:
        return df.groupby(by).agg(aggregations).reset_index()

    def join(
        self,
        left: pd.DataFrame,
        right: pd.DataFrame,
        on: list[str] | None,
        how: str,
        left_on: list[str] | None = None,
        right_on: list[str] | None = None,
        suffixes: tuple[str, str] = ("_x", "_y"),
    ) -> pd.DataFrame:
        how_arg = cast(Literal["left", "right", "outer", "inner", "cross"], how)
        if left_on and right_on:
            return left.merge(
                right, left_on=left_on, right_on=right_on, how=how_arg, suffixes=suffixes
            )
        return left.merge(right, on=on, how=how_arg, suffixes=suffixes)

    def concat(self, frames: list[pd.DataFrame]) -> pd.DataFrame:
        return pd.concat(frames, ignore_index=True)

    def limit_rows(self, df: pd.DataFrame, n: int, offset: int = 0) -> pd.DataFrame:
        return df.iloc[offset : offset + n]

    def replace_values(
        self, df: pd.DataFrame, column: str, to_replace: Any, value: Any, regex: bool = False
    ) -> pd.DataFrame:
        return df.assign(**{column: df[column].replace(to_replace, value, regex=regex)})

    def string_transform(
        self,
        df: pd.DataFrame,
        column: str,
        operation: str,
        find: str | None = None,
        replace_with: str | None = None,
        width: int | None = None,
        fill_char: str = " ",
        side: str = "left",
    ) -> pd.DataFrame:
        accessor = df[column].astype("string").str
        result: Any
        if operation == "lower":
            result = accessor.lower()
        elif operation == "upper":
            result = accessor.upper()
        elif operation == "strip":
            result = accessor.strip()
        elif operation == "title":
            result = accessor.title()
        elif operation == "capitalize":
            result = accessor.capitalize()
        elif operation == "len":
            result = accessor.len()
        elif operation == "replace":
            result = accessor.replace(cast(str, find), cast(str, replace_with), regex=False)
        elif operation == "pad":
            result = accessor.pad(
                cast(int, width), side=cast(Any, side), fillchar=fill_char
            )
        else:
            raise ValueError(f"Unknown string operation: {operation!r}")
        return df.assign(**{column: result})

    # -- New nodes (Phase 3) -------------------------------------------

    def sample_rows(
        self, df: pd.DataFrame, n: int | None, frac: float | None, seed: int | None
    ) -> pd.DataFrame:
        if frac is not None:
            return df.sample(frac=frac, random_state=seed)
        return df.sample(n=cast(int, n), random_state=seed)

    def remove_outliers(
        self,
        df: pd.DataFrame,
        columns: list[str],
        method: str,
        action: str,
        factor: float,
        threshold: float,
        lower: float,
        upper: float,
    ) -> pd.DataFrame:
        result = df.copy()
        keep = pd.Series(True, index=df.index)
        for col in columns:
            series = df[col]
            lo, hi = self._outlier_bounds(series, method, factor, threshold, lower, upper)
            if action == "clip":
                result[col] = series.clip(lo, hi)
            else:  # drop rows outside the bounds (keep nulls)
                keep &= series.between(lo, hi) | series.isna()
        return result if action == "clip" else df[keep]

    @staticmethod
    def _outlier_bounds(
        series: pd.Series,
        method: str,
        factor: float,
        threshold: float,
        lower: float,
        upper: float,
    ) -> tuple[float, float]:
        if method == "iqr":
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            return q1 - factor * iqr, q3 + factor * iqr
        if method == "zscore":
            mean, std = series.mean(), series.std()
            return mean - threshold * std, mean + threshold * std
        if method == "percentile":
            return series.quantile(lower / 100), series.quantile(upper / 100)
        raise ValueError(f"Unknown outlier method: {method!r}")

    def round_columns(
        self, df: pd.DataFrame, columns: list[str], decimals: int
    ) -> pd.DataFrame:
        return df.assign(**{c: df[c].round(decimals) for c in columns})

    def bin_column(
        self,
        df: pd.DataFrame,
        column: str,
        new_column: str,
        method: str,
        bins: int,
        labels: list[str] | None,
    ) -> pd.DataFrame:
        if method == "quantile":
            binned = pd.qcut(df[column], q=bins, labels=labels, duplicates="drop")
        else:
            binned = pd.cut(df[column], bins=bins, labels=labels)
        return df.assign(**{new_column: binned.astype("string")})

    def extract_date_parts(
        self, df: pd.DataFrame, column: str, parts: list[str]
    ) -> pd.DataFrame:
        ts = pd.to_datetime(df[column])
        accessors = {
            "year": ts.dt.year,
            "month": ts.dt.month,
            "day": ts.dt.day,
            "weekday": ts.dt.weekday,
            "hour": ts.dt.hour,
        }
        return df.assign(**{f"{column}_{p}": accessors[p] for p in parts})

    def unpivot(
        self,
        df: pd.DataFrame,
        id_vars: list[str],
        value_vars: list[str] | None,
        var_name: str,
        value_name: str,
    ) -> pd.DataFrame:
        return df.melt(
            id_vars=id_vars or None,
            value_vars=value_vars or None,
            var_name=var_name,
            value_name=value_name,
        )

    def pivot(
        self,
        df: pd.DataFrame,
        index: list[str],
        columns: str,
        values: str,
        aggfunc: str,
    ) -> pd.DataFrame:
        pivoted = df.pivot_table(
            index=index, columns=columns, values=values, aggfunc=cast(Any, aggfunc)
        )
        result: pd.DataFrame = pivoted.reset_index()
        result.columns = [str(c) for c in result.columns]
        return result
