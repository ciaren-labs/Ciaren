"""Window / analytics node: ranking, cumulative aggregates, and lag/lead over an
optional partition and order. Maps to pandas ``groupby`` + ordered ops and polars
``over``."""

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation

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

    def _pandas_value(self, config: dict[str, Any]) -> str:
        function, part, order, target, offset, desc, _ = self._args(config)
        grp = f"_w.groupby({part!r}, sort=False)" if part else None
        if function == "row_number":
            return f"{grp}.cumcount() + 1" if grp else "range(1, len(_w) + 1)"
        if function == "cumcount":
            return f"{grp}.cumcount()" if grp else "range(len(_w))"
        if function in _RANK_FUNCS:
            method = "dense" if function == "dense_rank" else "min"
            base = f"{grp}[{order[0]!r}]" if grp else f"_w[{order[0]!r}]"
            return f"{base}.rank(method={method!r}, ascending={not desc!r}).astype('int64')"
        if function in ("cumsum", "cummax", "cummin"):
            base = f"{grp}[{target!r}]" if grp else f"_w[{target!r}]"
            return f"{base}.{function}()"
        periods = offset if function == "lag" else -offset  # lag / lead
        base = f"{grp}[{target!r}]" if grp else f"_w[{target!r}]"
        return f"{base}.shift({periods})"

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        _, _, order, _, _, desc, new = self._args(config)
        lines = [f"_w = {src}.reset_index(drop=True)"]
        if order:
            asc = [not desc] * len(order)
            lines.append(f"_w = _w.sort_values(by={order!r}, ascending={asc!r}, kind='stable')")
        lines.append(f"_w = _w.assign(**{{{new!r}: {self._pandas_value(config)}}})")
        lines.append(f"{dst} = _w.sort_index().reset_index(drop=True)")
        return "\n".join(lines)

    def _polars_value(self, config: dict[str, Any]) -> str:
        function, part, order, target, offset, desc, _ = self._args(config)
        if function == "row_number":
            expr = "pl.int_range(1, pl.len() + 1)"
        elif function == "cumcount":
            expr = "pl.int_range(0, pl.len())"
        elif function in _RANK_FUNCS:
            method = "dense" if function == "dense_rank" else "min"
            expr = f"pl.col({order[0]!r}).rank(method={method!r}, descending={desc!r})"
        elif function in ("cumsum", "cummax", "cummin"):
            expr = f"pl.col({target!r}).{_CUM_POLARS[function]}()"
        else:  # lag / lead
            expr = f"pl.col({target!r}).shift({offset if function == 'lag' else -offset})"
        return f"{expr}.over({part!r})" if part else expr

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        _, _, order, _, _, desc, new = self._args(config)
        lines = [f"_w = {src}.with_row_index('__rn__')"]
        if order:
            lines.append(f"_w = _w.sort(by={order!r}, descending={desc!r})")
        lines.append(
            f"{dst} = _w.with_columns({self._polars_value(config)}.alias({new!r}))"
            ".sort('__rn__').drop('__rn__')"
        )
        return "\n".join(lines)
