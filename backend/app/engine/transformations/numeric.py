# SPDX-License-Identifier: AGPL-3.0-only
"""Numeric cleaning/shaping nodes: outlier handling, rounding, binning."""

from typing import Any, Callable

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


def _codegen_num(value: Any, cast: Callable[[Any], Any]) -> Any:
    """Coerce a numeric config value for code generation, but pass a flow-parameter
    reference (a ``CodeRef`` injected by the code generator) through untouched so it
    renders as a variable. Plain values and legacy strings are coerced as before."""
    if isinstance(value, (int, float, str)):
        return cast(value)
    return value


class RemoveOutliersTransformation(BaseTransformation):
    type = "removeOutliers"
    # The emitted polars loop computes per-column bounds via series subscripts
    # (df[_col].quantile(...)), which a LazyFrame doesn't support.
    polars_lazy_safe = False

    _METHODS = {"iqr", "zscore", "percentile"}
    _ACTIONS = {"drop", "clip"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("removeOutliers requires a non-empty 'columns' list")
        if config.get("method", "iqr") not in self._METHODS:
            raise ValueError(f"removeOutliers 'method' must be one of {sorted(self._METHODS)}")
        if config.get("action", "drop") not in self._ACTIONS:
            raise ValueError(f"removeOutliers 'action' must be one of {sorted(self._ACTIONS)}")

    def _params(self, config: dict[str, Any]) -> tuple[float, float, float, float]:
        return (
            float(config.get("factor", 1.5)),
            float(config.get("threshold", 3.0)),
            float(config.get("lower", 1.0)),
            float(config.get("upper", 99.0)),
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        factor, threshold, lower, upper = self._params(config)
        return {
            "out": engine.remove_outliers(
                inputs["in"],
                config["columns"],
                config.get("method", "iqr"),
                config.get("action", "drop"),
                factor,
                threshold,
                lower,
                upper,
            )
        }

    def _bounds_lines(self, config: dict[str, Any], series: str) -> str:
        """Lines (indented one loop-body level) that set ``lo, hi`` from ``series``."""
        method = config.get("method", "iqr")
        # Code generation only: pass parameter references through as variables.
        factor = _codegen_num(config.get("factor", 1.5), float)
        threshold = _codegen_num(config.get("threshold", 3.0), float)
        lower = _codegen_num(config.get("lower", 1.0), float)
        upper = _codegen_num(config.get("upper", 99.0), float)
        if method == "iqr":
            return (
                f"q1, q3 = {series}.quantile(0.25), {series}.quantile(0.75)\n"
                f"    iqr = q3 - q1\n"
                f"    lo, hi = q1 - {factor!r} * iqr, q3 + {factor!r} * iqr"
            )
        if method == "zscore":
            return (
                f"lo = {series}.mean() - {threshold!r} * {series}.std()\n"
                f"    hi = {series}.mean() + {threshold!r} * {series}.std()"
            )
        return f"lo, hi = {series}.quantile({lower!r} / 100), {series}.quantile({upper!r} / 100)"

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        action = config.get("action", "drop")
        bounds = self._bounds_lines(config, "s")
        header = f"{dst} = {src}.copy()" if action == "clip" else f"{dst} = {src}"
        body = f"{dst}[_col] = s.clip(lo, hi)" if action == "clip" else f"{dst} = {dst}[s.between(lo, hi) | s.isna()]"
        return f"{header}\nfor _col in {config['columns']!r}:\n    s = {dst}[_col]\n    {bounds}\n    {body}"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        action = config.get("action", "drop")
        bounds = self._bounds_lines(config, f"{dst}[_col]")
        body = (
            f"{dst} = {dst}.with_columns(pl.col(_col).clip(lo, hi))"
            if action == "clip"
            else f"{dst} = {dst}.filter(pl.col(_col).is_between(lo, hi) | pl.col(_col).is_null())"
        )
        return f"{dst} = {src}\nfor _col in {config['columns']!r}:\n    {bounds}\n    {body}"


class RoundNumbersTransformation(BaseTransformation):
    type = "roundNumbers"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("roundNumbers requires a non-empty 'columns' list")
        if not isinstance(config.get("decimals", 0), int):
            raise ValueError("roundNumbers 'decimals' must be an integer")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.round_columns(inputs["in"], config["columns"], int(config.get("decimals", 0)))}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        decimals = _codegen_num(config.get("decimals", 0), int)
        return f"{dst} = {src}.assign(**{{c: {src}[c].round({decimals!r}) for c in {config['columns']!r}}})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        decimals = _codegen_num(config.get("decimals", 0), int)
        return f"{dst} = {src}.with_columns([pl.col(c).round({decimals!r}) for c in {config['columns']!r}])"


class BinColumnTransformation(BaseTransformation):
    type = "binColumn"
    # equalwidth needs the column min/max as concrete numbers for .cut()'s
    # break list — computed via series subscripts a LazyFrame doesn't support.
    # (The flag is per node, so quantile mode materializes too.)
    polars_lazy_safe = False

    _METHODS = {"equalwidth", "quantile"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("binColumn requires a 'column'")
        if not config.get("new_column"):
            raise ValueError("binColumn requires a 'new_column' name")
        bins = config.get("bins", 4)
        if not isinstance(bins, int) or bins < 2:
            raise ValueError("binColumn 'bins' must be an integer >= 2")
        if config.get("method", "equalwidth") not in self._METHODS:
            raise ValueError(f"binColumn 'method' must be one of {sorted(self._METHODS)}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.bin_column(
                inputs["in"],
                config["column"],
                config["new_column"],
                config.get("method", "equalwidth"),
                int(config.get("bins", 4)),
                config.get("labels") or None,
            )
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, new = config["column"], config["new_column"]
        bins = _codegen_num(config.get("bins", 4), int)
        labels = config.get("labels") or None
        if config.get("method", "equalwidth") == "quantile":
            binned = f"pd.qcut({src}[{col!r}], q={bins!r}, labels={labels!r}, duplicates='drop')"
        else:
            binned = f"pd.cut({src}[{col!r}], bins={bins!r}, labels={labels!r})"
        return f"{dst} = {src}.assign(**{{{new!r}: {binned}.astype('string')}})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, new = config["column"], config["new_column"]
        bins = _codegen_num(config.get("bins", 4), int)
        labels = config.get("labels") or None
        if config.get("method", "equalwidth") == "quantile":
            quantiles = f"[i / {bins!r} for i in range(1, {bins!r})]"
            expr = f"pl.col({col!r}).qcut({quantiles}, labels={labels!r}, allow_duplicates=True)"
            return f"{dst} = {src}.with_columns({expr}.cast(pl.Utf8).alias({new!r}))"
        return (
            f"_lo, _hi = {src}[{col!r}].min(), {src}[{col!r}].max()\n"
            f"_breaks = [_lo + (_hi - _lo) / {bins!r} * i for i in range(1, {bins!r})]\n"
            f"{dst} = {src}.with_columns("
            f"pl.col({col!r}).cut(_breaks, labels={labels!r}).cast(pl.Utf8).alias({new!r}))"
        )
