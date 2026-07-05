# SPDX-License-Identifier: AGPL-3.0-only
"""Window / analytics node: ranking, cumulative aggregates, and lag/lead over an
optional partition and order. Maps to pandas ``groupby`` + ordered ops and polars
``over``."""

from typing import Any

from app.engine.backends.base import ROLLING_FUNCS, AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation, one_or_list, pd_assign_args


def _pd_sorted(order: list[str], descending: bool) -> str:
    """``_d`` sorted for a window computation: stable so ties keep input order,
    matching the engines. Ascending is pandas' default and omitted."""
    desc_arg = ", ascending=False" if descending else ""
    return f"_d.sort_values({one_or_list(order)!r}{desc_arg}, kind='stable')"


def _pl_over(part: list[str], order: list[str], descending: bool) -> str:
    """A polars ``.over(...)`` clause ordering rows within each window — the
    modern equivalent of the engine's row-index/sort/restore dance."""
    args = f"{one_or_list(part)!r}"
    if order:
        args += f", order_by={one_or_list(order)!r}"
        if descending:
            args += ", descending=True"
    return f".over({args})"


_ROLLING_POLARS = {
    "mean": "rolling_mean",
    "sum": "rolling_sum",
    "min": "rolling_min",
    "max": "rolling_max",
    "std": "rolling_std",
    "median": "rolling_median",
}

# Functions that rank by the order key (need a non-empty order_by).
_RANK_FUNCS = {"rank", "dense_rank"}
# Functions that operate on a value column (need a target).
_TARGET_FUNCS = {"cumsum", "cummax", "cummin", "lag", "lead"}
# Positional functions that need neither a target nor an order key.
_POSITIONAL = {"row_number", "cumcount"}
_ALL_FUNCS = _RANK_FUNCS | _TARGET_FUNCS | _POSITIONAL

_CUM_POLARS = {"cumsum": "cum_sum", "cummax": "cum_max", "cummin": "cum_min"}

# (function, partition_by, order_by, target, offset, descending, new_column)
_WindowArgs = tuple[str, list[str], list[str], str | None, int, bool, str]


class WindowFunctionTransformation(BaseTransformation):
    """Compute a window function into a new column.

    ``function`` is one of: ``row_number``, ``rank``, ``dense_rank``, ``cumcount``,
    ``cumsum``, ``cummax``, ``cummin``, ``lag``, ``lead``. ``partition_by`` scopes
    the window; ``order_by`` orders rows within it.
    """

    type = "windowFunction"

    def validate_config(self, config: dict[str, Any]) -> None:
        function = config.get("function")
        if function not in _ALL_FUNCS:
            raise ValueError(f"windowFunction 'function' must be one of {sorted(_ALL_FUNCS)}")
        if not config.get("new_column"):
            raise ValueError("windowFunction requires a 'new_column' name")
        if function in _TARGET_FUNCS and not config.get("target"):
            raise ValueError(f"windowFunction '{function}' requires a 'target' column")
        if function in _RANK_FUNCS and not config.get("order_by"):
            raise ValueError(f"windowFunction '{function}' requires a non-empty 'order_by'")
        if function in ("lag", "lead"):
            offset = config.get("offset", 1)
            if not isinstance(offset, int) or offset < 1:
                raise ValueError("windowFunction 'offset' must be an integer >= 1")

    def _args(self, config: dict[str, Any]) -> _WindowArgs:
        return (
            config["function"],
            config.get("partition_by") or [],
            config.get("order_by") or [],
            config.get("target"),
            int(config.get("offset", 1)),
            bool(config.get("descending", False)),
            config["new_column"],
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        function, partition_by, order_by, target, offset, descending, new = self._args(config)
        return {
            "out": engine.window_function(
                inputs["in"], function, partition_by, order_by, target, offset, descending, new
            )
        }

    # -- codegen --------------------------------------------------------

    def _pandas_value(self, config: dict[str, Any]) -> str | None:
        """The window value as a single ``_d``-rooted expression, or ``None`` when
        this configuration has no clean one-expression form.

        The trick that replaces the engine's sort → compute → restore dance:
        computing on ``_d.sort_values(...)`` yields a Series carrying the
        original index labels, so ``assign`` aligns it back to the input row
        order automatically. Rank functions don't even need the sort (min /
        dense ranks are order-independent, and pandas' groupby ``rank`` handles
        the partition), and ``method='first'`` reproduces stable row numbering
        over a single order column.
        """
        function, part, order, target, offset, desc, _ = self._args(config)
        asc_arg = ", ascending=False" if desc else ""
        sorted_d = _pd_sorted(order, desc) if order else "_d"
        grp = f"{sorted_d}.groupby({one_or_list(part)!r}, sort=False)" if part else sorted_d
        if function in _RANK_FUNCS:
            method = "dense" if function == "dense_rank" else "min"
            base = f"_d.groupby({one_or_list(part)!r}, sort=False)[{order[0]!r}]" if part else f"_d[{order[0]!r}]"
            return f"{base}.rank(method={method!r}{asc_arg}).astype('int64')"
        if function in ("row_number", "cumcount"):
            plus = " + 1" if function == "row_number" else ""
            if part:
                return f"{grp}.cumcount(){plus}"
            if not order:
                return "range(1, len(_d) + 1)" if function == "row_number" else "range(len(_d))"
            if len(order) == 1:
                # na_option='bottom' matches the engine's na_position='last'
                # sort: null order keys still get a number (default 'keep'
                # would yield NaN ranks and crash the int cast).
                base = f"_d[{order[0]!r}].rank(method='first', na_option='bottom'{asc_arg}).astype('int64')"
                return base if function == "row_number" else f"{base} - 1"
            return None  # multi-column order without partition: no one-liner
        if function in ("cumsum", "cummax", "cummin"):
            return f"{grp}[{target!r}].{function}()"
        periods = offset if function == "lag" else -offset  # lag / lead
        return f"{grp}[{target!r}].shift({periods})"

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        _, _, order, _, _, desc, new = self._args(config)
        value = self._pandas_value(config)
        if value is not None:
            return f"{dst} = {src}.assign({pd_assign_args({new: f'lambda _d: {value}'})})"
        # Fallback (positional numbering over a multi-column order without a
        # partition): sort, number, restore the original row order.
        asc = [not desc] * len(order)
        rng = "range(1, len(_w) + 1)" if config["function"] == "row_number" else "range(len(_w))"
        return (
            f"_w = {src}.reset_index(drop=True).sort_values(by={order!r}, ascending={asc!r}, kind='stable')\n"
            f"_w = _w.assign(**{{{new!r}: {rng}}})\n"
            f"{dst} = _w.sort_index().reset_index(drop=True)"
        )

    def _polars_expr(self, config: dict[str, Any]) -> str:
        function, part, order, target, offset, desc, _ = self._args(config)
        if function == "row_number":
            return "pl.int_range(1, pl.len() + 1)"
        if function == "cumcount":
            return "pl.int_range(0, pl.len())"
        if function in _RANK_FUNCS:
            desc_arg = ", descending=True" if desc else ""
            method = "dense" if function == "dense_rank" else "min"
            return f"pl.col({order[0]!r}).rank(method={method!r}{desc_arg})"
        if function in ("cumsum", "cummax", "cummin"):
            return f"pl.col({target!r}).{_CUM_POLARS[function]}()"
        return f"pl.col({target!r}).shift({offset if function == 'lag' else -offset})"  # lag / lead

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        function, part, order, _, _, desc, new = self._args(config)
        expr = self._polars_expr(config)
        # Rank never needs an over-ordering (min/dense ranks are order-independent);
        # everything else orders within the window via .over(order_by=...), which
        # computes on the ordered rows and restores the frame's own order — the
        # one-expression form of the engine's row-index/sort/restore.
        if function in _RANK_FUNCS:
            over = f".over({one_or_list(part)!r})" if part else ""
            return f"{dst} = {src}.with_columns({expr}{over}.alias({new!r}))"
        if part:
            return f"{dst} = {src}.with_columns({expr}{_pl_over(part, order, desc)}.alias({new!r}))"
        if not order:
            return f"{dst} = {src}.with_columns({expr}.alias({new!r}))"
        # No partition to hang .over(order_by=...) on: sort, compute, restore.
        lines = [
            f"_w = {src}.with_row_index('__rn__')",
            f"_w = _w.sort(by={order!r}, descending={desc!r})",
            f"{dst} = _w.with_columns({expr}.alias({new!r})).sort('__rn__').drop('__rn__')",
        ]
        return "\n".join(lines)


class RollingAggregateTransformation(BaseTransformation):
    """Moving aggregate (mean/sum/min/max/std/median) over a window of N rows,
    within an optional partition and ordered by one or more columns."""

    type = "rollingAggregate"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("target"):
            raise ValueError("rollingAggregate requires a 'target' column")
        function = config.get("function")
        if function not in ROLLING_FUNCS:
            raise ValueError(f"rollingAggregate 'function' must be one of {sorted(ROLLING_FUNCS)}")
        window = config.get("window")
        if not isinstance(window, int) or isinstance(window, bool) or window < 1:
            raise ValueError("rollingAggregate 'window' must be an integer >= 1")
        mp = config.get("min_periods")
        if mp is not None and (not isinstance(mp, int) or isinstance(mp, bool) or mp < 1):
            raise ValueError("rollingAggregate 'min_periods' must be a positive integer or null")
        if not config.get("new_column"):
            raise ValueError("rollingAggregate requires a 'new_column' name")

    def _args(self, config: dict[str, Any]) -> tuple[str, str, int, int | None, list[str], list[str], bool, str]:
        return (
            config["target"],
            config["function"],
            int(config["window"]),
            config.get("min_periods"),
            config.get("partition_by") or [],
            config.get("order_by") or [],
            bool(config.get("descending", False)),
            config["new_column"],
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        target, function, window, min_periods, partition_by, order_by, descending, new = self._args(config)
        return {
            "out": engine.rolling_aggregate(
                inputs["in"], target, function, window, min_periods, partition_by, order_by, descending, new
            )
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        target, function, window, min_periods, partition_by, order_by, descending, new = self._args(config)
        base = _pd_sorted(order_by, descending) if order_by else "_d"
        mp = f", min_periods={min_periods!r}" if min_periods is not None else ""
        roll = f".rolling({window!r}{mp})"
        if partition_by:
            levels = 0 if len(partition_by) == 1 else list(range(len(partition_by)))
            value = (
                f"{base}.groupby({one_or_list(partition_by)!r}, sort=False)[{target!r}]{roll}.{function}()"
                f".reset_index(level={levels!r}, drop=True)"
            )
        else:
            value = f"{base}[{target!r}]{roll}.{function}()"
        # Computing on the sorted view keeps the original index labels, so
        # assign aligns the result back to the input row order.
        return f"{dst} = {src}.assign({pd_assign_args({new: f'lambda _d: {value}'})})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        target, function, window, min_periods, partition_by, order_by, descending, new = self._args(config)
        mp = f", min_samples={min_periods!r}" if min_periods is not None else ""
        expr = f"pl.col({target!r}).{_ROLLING_POLARS[function]}(window_size={window!r}{mp})"
        if partition_by:
            return f"{dst} = {src}.with_columns({expr}{_pl_over(partition_by, order_by, descending)}.alias({new!r}))"
        if not order_by:
            return f"{dst} = {src}.with_columns({expr}.alias({new!r}))"
        lines = [
            f"_w = {src}.with_row_index('__rn__')",
            f"_w = _w.sort(by={order_by!r}, descending={descending!r})",
            f"{dst} = _w.with_columns({expr}.alias({new!r})).sort('__rn__').drop('__rn__')",
        ]
        return "\n".join(lines)


class RowDifferenceTransformation(BaseTransformation):
    """Difference (or percent change) between consecutive rows of a column, within an
    optional partition and order. Useful for deltas and growth rates over time."""

    type = "rowDifference"
    _METHODS = {"diff", "pct_change"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("target"):
            raise ValueError("rowDifference requires a 'target' column")
        method = config.get("method", "diff")
        if method not in self._METHODS:
            raise ValueError(f"rowDifference 'method' must be one of {sorted(self._METHODS)}")
        periods = config.get("periods", 1)
        if not isinstance(periods, int) or isinstance(periods, bool) or periods < 1:
            raise ValueError("rowDifference 'periods' must be an integer >= 1")
        if not config.get("new_column"):
            raise ValueError("rowDifference requires a 'new_column' name")

    def _args(self, config: dict[str, Any]) -> tuple[str, str, int, list[str], list[str], bool, str]:
        return (
            config["target"],
            config.get("method", "diff"),
            int(config.get("periods", 1)),
            config.get("partition_by") or [],
            config.get("order_by") or [],
            bool(config.get("descending", False)),
            config["new_column"],
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        target, method, periods, partition_by, order_by, descending, new = self._args(config)
        return {
            "out": engine.row_difference(inputs["in"], target, method, periods, partition_by, order_by, descending, new)
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        target, method, periods, partition_by, order_by, descending, new = self._args(config)
        sorted_d = _pd_sorted(order_by, descending) if order_by else "_d"
        base = (
            f"{sorted_d}.groupby({one_or_list(partition_by)!r}, sort=False)[{target!r}]"
            if partition_by
            else f"{sorted_d}[{target!r}]"
        )
        periods_arg = f"{periods!r}" if periods != 1 else ""  # 1 is the pandas default
        value = f"{base}.{method}({periods_arg})"
        # Sorted-view computation + assign's index alignment restores row order.
        return f"{dst} = {src}.assign({pd_assign_args({new: f'lambda _d: {value}'})})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        target, method, periods, partition_by, order_by, descending, new = self._args(config)
        call = "pct_change" if method == "pct_change" else "diff"
        periods_arg = f"{periods!r}" if periods != 1 else ""  # 1 is the polars default
        expr = f"pl.col({target!r}).{call}({periods_arg})"
        if partition_by:
            return f"{dst} = {src}.with_columns({expr}{_pl_over(partition_by, order_by, descending)}.alias({new!r}))"
        if not order_by:
            return f"{dst} = {src}.with_columns({expr}.alias({new!r}))"
        lines = [
            f"_w = {src}.with_row_index('__rn__')",
            f"_w = _w.sort(by={order_by!r}, descending={descending!r})",
            f"{dst} = _w.with_columns({expr}.alias({new!r})).sort('__rn__').drop('__rn__')",
        ]
        return "\n".join(lines)
