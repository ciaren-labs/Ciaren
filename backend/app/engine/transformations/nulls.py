# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation, one_or_list, pd_assign_args, pl_exprs_arg


class DropNullsTransformation(BaseTransformation):
    type = "dropNulls"

    def validate_config(self, config: dict[str, Any]) -> None:
        how = config.get("how", "any")
        if how not in ("any", "all"):
            raise ValueError("dropNulls 'how' must be 'any' or 'all'.")

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
            args.append(f"subset={one_or_list(subset)!r}")
        if how != "any":
            args.append(f"how={how!r}")
        return f"{dst} = {src}.dropna({', '.join(args)})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        subset = config.get("subset")
        how = config.get("how", "any")
        if how == "all":
            cols = subset or "all columns"
            # collect_schema().names() works on DataFrame and LazyFrame alike
            # (LazyFrame.columns raises PerformanceWarning, removal candidate).
            cols_expr = f"{subset!r}" if subset else f"{src}.collect_schema().names()"
            return (
                f"{dst} = {src}.filter(~pl.all_horizontal("
                f"[pl.col(c).is_null() for c in {cols_expr}]))  # drop rows all-null in {cols}"
            )
        if subset:
            return f"{dst} = {src}.drop_nulls(subset={one_or_list(subset)!r})"
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
    # Strategy -> the pandas expression computing the fill value for a series
    # ``{s}``. mode: Series.mode() is sorted, so iloc[0] is the smallest —
    # matching the engines' deterministic tie-break for every dtype a flow can
    # build. (A categorical column loaded from parquet sorts modes by category
    # order here; the engines use the lexicographic smallest — accepted corner.)
    _STRATEGY_FILL = {
        "mean": "{s}.mean()",
        "median": "{s}.median()",
        "min": "{s}.min()",
        "max": "{s}.max()",
        "mode": "{s}.mode().iloc[0]",
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
            raise ValueError(f"fillNulls 'strategy' must be one of {sorted(self._VALID_STRATEGIES)}.")
        if strategy == "constant" and "value" not in config:
            raise ValueError("fillNulls 'constant' strategy requires a 'value'.")

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
                # fillna(dict) silently skips a column the frame doesn't have
                # (the app run raises KeyError) — accepted: the value-computing
                # strategies below still raise via their {src}[col] reads.
                fills = ", ".join(f"{c!r}: {value!r}" for c in columns)
                return f"{dst} = {src}.fillna({{{fills}}})"
            return f"{dst} = {src}.fillna({value!r})"

        if strategy in ("ffill", "bfill"):
            if columns:
                items = {c: f"{src}[{c!r}].{strategy}()" for c in columns}
                return f"{dst} = {src}.assign({pd_assign_args(items)})"
            return f"{dst} = {src}.{strategy}()"

        if columns:
            # Explicit user-selected columns: fill each one directly, the way a
            # person would. No dtype guard here — the user picked these columns,
            # so e.g. median on a text column should fail loudly in the script
            # (the app run skips it; see the all-columns branch below).
            fills = ", ".join(f"{c!r}: {self._STRATEGY_FILL[strategy].format(s=f'{src}[{c!r}]')}" for c in columns)
            return f"{dst} = {src}.fillna({{{fills}}})"

        # All-columns mode iterates whatever the frame has, so mirror
        # PandasEngine.fill_nulls' skips or the exported script crashes where
        # the app run succeeds: mean/median only fill numeric columns (median
        # of a string column raises), and mode skips columns with no non-null
        # values (mode().iloc[0] on an empty result is an IndexError).
        guard = ""
        if strategy in ("mean", "median"):
            guard = f" if pd.api.types.is_numeric_dtype({src}[c])"
        elif strategy == "mode":
            guard = f" if not {src}[c].mode().empty"
        fill_expr = self._STRATEGY_FILL[strategy].format(s=f"{src}[c]")
        return f"{dst} = {src}.assign(**{{c: {src}[c].fillna({fill_expr}) for c in {src}.columns{guard}}})"

    # Per-column polars fill expressions, by strategy, for explicit user-picked
    # columns. mode drops nulls first (with nulls present, null itself can be
    # the mode) and takes min() so multi-modal ties are reproducible and match
    # pandas' sorted mode.
    _POLARS_FILL = {
        "mean": "pl.col({c}).fill_null(strategy='mean')",
        "min": "pl.col({c}).fill_null(strategy='min')",
        "max": "pl.col({c}).fill_null(strategy='max')",
        "zero": "pl.col({c}).fill_null(strategy='zero')",
        "ffill": "pl.col({c}).fill_null(strategy='forward')",
        "bfill": "pl.col({c}).fill_null(strategy='backward')",
        "median": "pl.col({c}).fill_null(pl.col({c}).median())",
        "mode": "pl.col({c}).fill_null(pl.col({c}).drop_nulls().mode().min())",
    }

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns = config.get("columns")
        strategy = config.get("strategy", "constant")

        if strategy == "constant":
            value = config.get("value")
            if columns:
                exprs = [f"pl.col({c!r}).fill_null({value!r})" for c in columns]
                return f"{dst} = {src}.with_columns({pl_exprs_arg(exprs)})"
            return f"{dst} = {src}.fill_null({value!r})"

        if columns:
            # Explicit user-selected columns: one expression per column, no
            # schema guard — same loud-failure trade-off as the pandas emitter.
            exprs = [self._POLARS_FILL[strategy].format(c=repr(c)) for c in columns]
            return f"{dst} = {src}.with_columns({pl_exprs_arg(exprs)})"

        if strategy in ("ffill", "bfill"):
            # Frame-level fill: identical to filling every column (what the
            # engine does), and reads the way a person would write it.
            strat = self._POLARS_STRATEGY[strategy]
            return f"{dst} = {src}.fill_null(strategy={strat!r})"
        # collect_schema().names(), not .columns: it works identically on a
        # DataFrame and a LazyFrame (where .columns raises PerformanceWarning
        # and is slated for removal), so one emitted form serves both modes.
        if strategy in self._POLARS_STRATEGY:
            strat = self._POLARS_STRATEGY[strategy]
            # Mean only exists for numbers — mirror the engine's skip of other
            # columns (see PolarsEngine.fill_nulls) with a schema guard.
            if strategy == "mean":
                return (
                    f"_sch = {src}.collect_schema()\n"
                    f"{dst} = {src}.with_columns([pl.col(c).fill_null(strategy={strat!r}) "
                    f"for c in _sch.names() if _sch[c].is_numeric()])"
                )
            return (
                f"{dst} = {src}.with_columns([pl.col(c).fill_null(strategy={strat!r}) "
                f"for c in {src}.collect_schema().names()])"
            )
        # median / mode as pure expressions: no {src}[c] series subscripts, so
        # the emitted code also runs on a LazyFrame in lazy mode.
        if strategy == "median":
            # The engine skips columns whose Series.median() is None (strings,
            # categoricals); the *expression* median raises on those dtypes, so
            # mirror the skip with a schema guard. Boolean/Null stay included:
            # there the expression behaves like the engine (raise / no-op).
            return (
                f"_sch = {src}.collect_schema()\n"
                f"{dst} = {src}.with_columns([pl.col(c).fill_null(pl.col(c).median()) for c in _sch.names() "
                f"if _sch[c].is_numeric() or _sch[c].is_temporal() or _sch[c] in (pl.Boolean, pl.Null)])"
            )
        # mode across all columns: null-mode/tie handling as in _POLARS_FILL;
        # an all-null column's mode().min() is null and filling nulls with null
        # is a no-op — left untouched, mirroring PolarsEngine.fill_nulls.
        return (
            f"{dst} = {src}.with_columns([pl.col(c).fill_null(pl.col(c).drop_nulls().mode().min()) "
            f"for c in {src}.collect_schema().names()])"
        )
