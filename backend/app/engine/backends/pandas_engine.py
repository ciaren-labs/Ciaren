from __future__ import annotations

import json
from typing import Any, Literal, cast

import numpy as np
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

    # -- New nodes (text/date/value mapping) ---------------------------

    def split_column(
        self,
        df: pd.DataFrame,
        column: str,
        into: list[str],
        mode: str,
        delimiter: str,
        pattern: str,
        keep_original: bool,
    ) -> pd.DataFrame:
        src = df[column].astype("string")
        if mode == "regex":
            parts = src.str.extract(pattern)
        else:
            parts = src.str.split(delimiter, expand=True, regex=False)
        assignments: dict[str, Any] = {
            name: (parts[i] if i in parts.columns else pd.NA)
            for i, name in enumerate(into)
        }
        result = df.assign(**assignments)
        if not keep_original and column not in into:
            result = result.drop(columns=[column])
        return result

    def parse_dates(
        self, df: pd.DataFrame, columns: list[str], fmt: str | None, errors: str
    ) -> pd.DataFrame:
        err: Literal["raise", "coerce"] = "coerce" if errors == "coerce" else "raise"
        return df.assign(
            **{c: pd.to_datetime(df[c], format=fmt or None, errors=err) for c in columns}
        )

    def map_values(
        self,
        df: pd.DataFrame,
        column: str,
        new_column: str | None,
        mapping: dict[Any, Any],
        default: Any,
        use_default: bool,
    ) -> pd.DataFrame:
        target = new_column or column
        if use_default:
            mapped = df[column].map(mapping).where(df[column].isin(mapping), default)
        else:
            # Unmapped values keep their original value.
            mapped = df[column].replace(mapping)
        return df.assign(**{target: mapped})

    def window_function(
        self,
        df: pd.DataFrame,
        function: str,
        partition_by: list[str],
        order_by: list[str],
        target: str | None,
        offset: int,
        descending: bool,
        new_column: str,
    ) -> pd.DataFrame:
        # Work on a positional copy so we can restore the original row order
        # after computing the (order-sensitive) window values.
        work = df.reset_index(drop=True)
        if order_by:
            work = work.sort_values(
                by=order_by, ascending=[not descending] * len(order_by), kind="stable"
            )
        values = self._window_values(
            work, function, partition_by, order_by, target, offset, descending
        )
        work = work.assign(**{new_column: values})
        return work.sort_index().reset_index(drop=True)

    @staticmethod
    def _window_values(
        work: pd.DataFrame,
        function: str,
        partition_by: list[str],
        order_by: list[str],
        target: str | None,
        offset: int,
        descending: bool,
    ) -> Any:
        grouped = work.groupby(partition_by, sort=False) if partition_by else None
        if function == "row_number":
            return grouped.cumcount() + 1 if grouped is not None else range(1, len(work) + 1)
        if function == "cumcount":
            return grouped.cumcount() if grouped is not None else range(len(work))
        if function in ("rank", "dense_rank"):
            method: Any = "dense" if function == "dense_rank" else "min"
            key = order_by[0]
            ranked = (
                grouped[key].rank(method=method, ascending=not descending)
                if grouped is not None
                else work[key].rank(method=method, ascending=not descending)
            )
            return ranked.astype("int64")
        if function in ("cumsum", "cummax", "cummin"):
            series = grouped[cast(str, target)] if grouped is not None else work[cast(str, target)]
            return getattr(series, function)()
        if function in ("lag", "lead"):
            periods = offset if function == "lag" else -offset
            series = grouped[cast(str, target)] if grouped is not None else work[cast(str, target)]
            return series.shift(periods)
        raise ValueError(f"Unknown window function: {function!r}")

    def conditional_column(
        self,
        df: pd.DataFrame,
        rules: list[dict[str, Any]],
        default: Any,
        new_column: str,
    ) -> pd.DataFrame:
        conditions = [
            _pandas_condition_mask(df, r["column"], r.get("operator", "=="), r.get("value"))
            for r in rules
        ]
        choices = [r.get("result") for r in rules]
        # np.select picks the first matching condition (CASE-WHEN priority order).
        result = np.select(conditions, choices, default=default)  # type: ignore[type-var]
        return df.assign(**{new_column: result})


def _pandas_condition_mask(
    df: pd.DataFrame, column: str, operator: str, value: Any
) -> pd.Series:
    """Boolean mask for one conditionalColumn rule (mirrors filter operators)."""
    col = df[column]
    mask: Any
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
            raise ValueError(f"Unknown condition operator: {operator!r}")
    return cast("pd.Series", mask)
