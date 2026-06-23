from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


class DropNullsTransformation(BaseTransformation):
    type = "dropNulls"

    def validate_config(self, config: dict[str, Any]) -> None:
        how = config.get("how", "any")
        if how not in ("any", "all"):
            raise ValueError("dropNulls 'how' must be 'any' or 'all'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        subset = config.get("subset") or None
        how = config.get("how", "any")
        return {"out": engine.drop_nulls(inputs["in"], subset, how)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src = input_vars["in"]
        dst = output_vars["out"]
        subset = config.get("subset")
        how = config.get("how", "any")
        args = []
        if subset:
            args.append(f"subset={subset!r}")
        if how != "any":
            args.append(f"how={how!r}")
        return f"{dst} = {src}.dropna({', '.join(args)})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        subset = config.get("subset")
        how = config.get("how", "any")
        if how == "all":
            cols = subset or f"{src}.columns"
            cols_expr = f"{subset!r}" if subset else f"{src}.columns"
            return (
                f"{dst} = {src}.filter(~pl.all_horizontal("
                f"[pl.col(c).is_null() for c in {cols_expr}]))  # drop rows all-null in {cols}"
            )
        if subset:
            return f"{dst} = {src}.drop_nulls(subset={subset!r})"
        return f"{dst} = {src}.drop_nulls()"


class FillNullsTransformation(BaseTransformation):
    type = "fillNulls"

    _VALID_STRATEGIES = {
        "constant",
        "mean",
        "median",
        "mode",
        "min",
        "max",
        "zero",
        "ffill",
        "bfill",
    }
    # Strategy -> the per-column pandas expression that computes the fill value.
    _STRATEGY_FILL = {
        "mean": "{s}[c].mean()",
        "median": "{s}[c].median()",
        "min": "{s}[c].min()",
        "max": "{s}[c].max()",
        "mode": "{s}[c].mode().iloc[0]",
        "zero": "0",
    }
    # Strategies polars' fill_null accepts directly via strategy=...
    _POLARS_STRATEGY = {
        "mean": "mean",
        "min": "min",
        "max": "max",
        "zero": "zero",
        "ffill": "forward",
        "bfill": "backward",
    }

    def validate_config(self, config: dict[str, Any]) -> None:
        strategy = config.get("strategy", "constant")
        if strategy not in self._VALID_STRATEGIES:
            raise ValueError(f"fillNulls 'strategy' must be one of {sorted(self._VALID_STRATEGIES)}")
        if strategy == "constant" and "value" not in config:
            raise ValueError("fillNulls with the 'constant' strategy requires a 'value'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        columns = config.get("columns") or None
        strategy = config.get("strategy", "constant")
        return {"out": engine.fill_nulls(inputs["in"], columns, strategy, config.get("value"))}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns = config.get("columns")
        strategy = config.get("strategy", "constant")

        if strategy == "constant":
            value = config.get("value")
            if columns:
                return f"{dst} = {src}.assign(**{{c: {src}[c].fillna({value!r}) for c in {columns!r}}})"
            return f"{dst} = {src}.fillna({value!r})"

        cols = columns or "all columns"
        target = f"{columns!r}" if columns else f"{src}.columns"
        if strategy in ("ffill", "bfill"):
            method = strategy
            return f"{dst} = {src}.assign(**{{c: {src}[c].{method}() for c in {target}}})  # fill nulls ({cols})"
        fill_expr = self._STRATEGY_FILL[strategy].format(s=src)
        return (
            f"{dst} = {src}.assign(**{{c: {src}[c].fillna({fill_expr}) for c in {target}}})  # {strategy} fill ({cols})"
        )

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns = config.get("columns")
        strategy = config.get("strategy", "constant")
        cols_iter = f"{columns!r}" if columns else f"{src}.columns"

        if strategy == "constant":
            value = config.get("value")
            if columns:
                return f"{dst} = {src}.with_columns([pl.col(c).fill_null({value!r}) for c in {columns!r}])"
            return f"{dst} = {src}.fill_null({value!r})"
        if strategy in self._POLARS_STRATEGY:
            strat = self._POLARS_STRATEGY[strategy]
            return f"{dst} = {src}.with_columns([pl.col(c).fill_null(strategy={strat!r}) for c in {cols_iter}])"
        # median / mode: compute the value per column, then fill.
        agg = "median" if strategy == "median" else "mode().first"
        return f"{dst} = {src}.with_columns([pl.col(c).fill_null({src}[c].{agg}()) for c in {cols_iter}])"
