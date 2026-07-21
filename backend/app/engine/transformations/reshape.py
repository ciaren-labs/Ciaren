# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import (
    BaseTransformation,
    is_safe_kwarg,
    one_or_list,
    pd_assign_args,
    pl_exprs_arg,
    polars_to_datetime_expr,
)


class GroupByAggregateTransformation(BaseTransformation):
    type = "groupByAggregate"

    # Aggregation name -> the polars expression suffix (applied to pl.col(col))
    # that implements it. Keys use the pandas-facing names the config carries;
    # every one matches pandas' groupby().agg(<name>) numeric AND null semantics,
    # so the run-path polars engine (PolarsEngine._AGG_FUNCS) and this exported
    # polars script agree with pandas. In particular pandas' 'first'/'last' SKIP
    # NA and 'nunique' EXCLUDES NA, so drop_nulls() precedes those aggregations
    # (an all-null group then yields null / 0, matching pandas). A consistency
    # test pins these to _AGG_FUNCS so the two representations can't drift.
    _POLARS_AGG = {
        "sum": "sum()",
        "mean": "mean()",
        "count": "count()",
        "min": "min()",
        "max": "max()",
        "median": "median()",
        "std": "std()",
        "var": "var()",
        "prod": "product()",
        "first": "drop_nulls().first()",
        "last": "drop_nulls().last()",
        "nunique": "drop_nulls().n_unique()",
    }

    # pandas' groupby().agg(name) accepts any reducer pandas knows (e.g. "sem",
    # "skew", "kurt", "size"), but the polars run-path (_AGG_FUNCS) and the
    # exported polars script only implement _POLARS_AGG. A flow always exports
    # both a pandas and a polars script and can be re-run on either engine, so
    # aggfuncs are restricted here to the shared set — otherwise a config that
    # validates and runs on pandas would fail (or silently diverge) on polars.
    # Mirrors PivotTransformation._SHARED_AGGFUNCS.
    _SHARED_AGGFUNCS = frozenset(_POLARS_AGG)

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("group_by"):
            raise ValueError("groupByAggregate requires 'group_by' list")
        aggregations = config.get("aggregations")
        if not aggregations:
            raise ValueError("groupByAggregate requires 'aggregations' dict {col: func}")
        invalid = {func for func in aggregations.values() if func not in self._SHARED_AGGFUNCS}
        if invalid:
            raise ValueError(
                f"groupByAggregate 'aggregations' function(s) {sorted(invalid)} not supported on "
                f"both engines; use one of {sorted(self._SHARED_AGGFUNCS)}"
            )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.groupby_agg(inputs["in"], config["group_by"], config["aggregations"])
        return {"out": result}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        by = one_or_list(config["group_by"])
        return f"{dst} = {src}.groupby({by!r}).agg({config['aggregations']!r}).reset_index()"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        by = one_or_list(config["group_by"])
        # No .alias(): every mapped agg expression keeps its column's name.
        aggs = [
            f"pl.col({col!r}).{self._POLARS_AGG.get(func, f'{func}()')}" for col, func in config["aggregations"].items()
        ]
        return f"{dst} = {src}.group_by({by!r}).agg({pl_exprs_arg(aggs)})"


class ConcatRowsTransformation(BaseTransformation):
    type = "concatRows"
    multi_input = True

    def validate_config(self, config: dict[str, Any]) -> None:
        pass

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frames = list(inputs.values())
        return {"out": engine.concat(frames)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        dst = output_vars["out"]
        src_list = list(input_vars.values())
        return f"{dst} = pd.concat([{', '.join(src_list)}], ignore_index=True)"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        dst = output_vars["out"]
        srcs = ", ".join(input_vars.values())
        # diagonal_relaxed matches execute() (see PolarsEngine.concat) and pandas'
        # pd.concat(ignore_index=True): it unions columns (null-filling missing
        # ones) and relaxes dtypes. Plain vertical concat is schema-strict and
        # would fail where the app succeeds (mismatched columns or int+float).
        return f"{dst} = pl.concat([{srcs}], how='diagonal_relaxed')"


class CreateCalculatedColumnTransformation(BaseTransformation):
    type = "calculatedColumn"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column_name"):
            raise ValueError("calculatedColumn requires 'column_name'")
        if not config.get("expression"):
            raise ValueError("calculatedColumn requires 'expression'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.add_column(inputs["in"], config["column_name"], config["expression"])
        return {"out": result}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column_name"]
        expr = config["expression"]
        # eval's assignment form is the cleanest spelling and computes exactly
        # what the engine does (df.eval(expr) assigned to the column). It needs
        # a literal, single-line expression and an identifier target; otherwise
        # fall back to a chainable assign-with-callable (`_d`: `_` names are
        # reserved away from flow parameters).
        if is_safe_kwarg(col) and isinstance(expr, str) and "\n" not in expr:
            return f"{dst} = {src}.eval({f'{col} = {expr}'!r})"
        return f"{dst} = {src}.assign(**{{{col!r}: lambda _d: _d.eval({expr!r})}})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, expr = config["column_name"], config["expression"]
        # pl.sql_expr handles arithmetic expressions like "price * quantity".
        return f"{dst} = {src}.with_columns(pl.sql_expr({expr!r}).alias({col!r}))"


class ExtractDatePartsTransformation(BaseTransformation):
    type = "extractDateParts"

    _VALID_PARTS = {"year", "month", "day", "weekday", "hour"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("extractDateParts requires a 'column'")
        parts = config.get("parts")
        if not parts:
            raise ValueError("extractDateParts requires a non-empty 'parts' list")
        invalid = set(parts) - self._VALID_PARTS
        if invalid:
            raise ValueError(f"extractDateParts has unknown part(s): {sorted(invalid)}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.extract_date_parts(inputs["in"], config["column"], config["parts"])}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, parts = config["column"], config["parts"]
        # col + "_" + p, not an f-string: a parameterized column arrives as a
        # CodeRef whose + composes source; f-string interpolation would freeze
        # the variable's *name* into the emitted column names.
        items = {col + "_" + p: f"_dt.dt.{p}" for p in parts}
        return f"_dt = pd.to_datetime({src}[{col!r}])\n{dst} = {src}.assign({pd_assign_args(items)})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, parts = config["column"], config["parts"]
        # polars weekday is Monday=1..Sunday=7; subtract 1 to match pandas (Monday=0).
        exprs = ", ".join(
            f"(_dt.dt.weekday() - 1).alias({(col + '_' + p)!r})"
            if p == "weekday"
            else f"_dt.dt.{p}().alias({(col + '_' + p)!r})"
            for p in parts
        )
        return (
            f"_sch = {src}.collect_schema()\n"
            f"_dt = {polars_to_datetime_expr('_sch', repr(col))}\n"
            f"{dst} = {src}.with_columns([{exprs}])"
        )


class ParseDatesTransformation(BaseTransformation):
    """Parse string columns into datetimes, with optional format and coercion."""

    type = "parseDates"

    _ERRORS = {"raise", "coerce"}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("parseDates requires a non-empty 'columns' list")
        if config.get("errors", "coerce") not in self._ERRORS:
            raise ValueError(f"parseDates 'errors' must be one of {sorted(self._ERRORS)}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.parse_dates(
                inputs["in"],
                config["columns"],
                config.get("format") or None,
                config.get("errors", "coerce"),
            )
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        fmt = config.get("format") or None
        errors = config.get("errors", "coerce")
        kwargs = ""
        if fmt:
            kwargs += f", format={fmt!r}"
        if errors != "raise":  # pandas' own default
            kwargs += f", errors={errors!r}"
        if len(cols) <= 3:
            # One parse per column, spelled out — callables so the statement chains.
            items = {c: f"lambda _d: pd.to_datetime(_d[{c!r}]{kwargs})" for c in cols}
            return f"{dst} = {src}.assign({pd_assign_args(items)})"
        return f"{dst} = {src}.assign(**{{c: pd.to_datetime({src}[c]{kwargs}) for c in {cols!r}}})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        fmt = config.get("format") or None
        strict = config.get("errors", "coerce") != "coerce"
        if len(cols) == 1 and isinstance(cols[0], str):
            # Both dispatch branches keep the column's name — no alias needed.
            expr = polars_to_datetime_expr("_sch", repr(cols[0]), fmt=fmt, strict=strict)
            return f"_sch = {src}.collect_schema()\n{dst} = {src}.with_columns({expr})"
        expr = polars_to_datetime_expr("_sch", "c", fmt=fmt, strict=strict)
        return f"_sch = {src}.collect_schema()\n{dst} = {src}.with_columns([{expr}.alias(c) for c in {cols!r}])"


class UnpivotTransformation(BaseTransformation):
    type = "unpivot"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("id_vars"):
            raise ValueError("unpivot requires a non-empty 'id_vars' list (columns to keep)")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.unpivot(
                inputs["in"],
                config["id_vars"],
                config.get("value_vars") or None,
                config.get("var_name", "variable"),
                config.get("value_name", "value"),
            )
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        args = f"id_vars={config['id_vars']!r}"
        if config.get("value_vars"):
            args += f", value_vars={config['value_vars']!r}"
        if config.get("var_name", "variable") != "variable":  # pandas' own default
            args += f", var_name={config['var_name']!r}"
        if config.get("value_name", "value") != "value":  # pandas' own default
            args += f", value_name={config['value_name']!r}"
        return f"{dst} = {src}.melt({args})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        args = f"index={config['id_vars']!r}"
        if config.get("value_vars"):
            args += f", on={config['value_vars']!r}"
        if config.get("var_name", "variable") != "variable":  # polars' own default
            args += f", variable_name={config['var_name']!r}"
        if config.get("value_name", "value") != "value":  # polars' own default
            args += f", value_name={config['value_name']!r}"
        return f"{dst} = {src}.unpivot({args})"


class PivotTransformation(BaseTransformation):
    type = "pivot"
    polars_lazy_safe = False  # LazyFrame has no .pivot()

    # pandas' pivot_table(aggfunc=...) accepts any reducer name pandas knows
    # (e.g. "std", "var", "nunique"), but polars' DataFrame.pivot(aggregate_function=...)
    # only implements this fixed set. A flow always exports both a pandas and a
    # polars script (and can be re-run on either engine), so aggfunc is restricted
    # here to what both support — otherwise a config that validates and runs fine
    # on pandas can fail outright the moment the same flow runs on polars.
    _SHARED_AGGFUNCS = {"sum", "mean", "min", "max", "median", "first", "last", "count"}

    def validate_config(self, config: dict[str, Any]) -> None:
        for key in ("index", "columns", "values"):
            if not config.get(key):
                raise ValueError(f"pivot requires '{key}'")
        aggfunc = config.get("aggfunc", "sum")
        if aggfunc not in self._SHARED_AGGFUNCS:
            raise ValueError(f"pivot 'aggfunc' must be one of {sorted(self._SHARED_AGGFUNCS)}, got {aggfunc!r}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        index = config["index"]
        index = [index] if isinstance(index, str) else index
        return {
            "out": engine.pivot(
                inputs["in"],
                index,
                config["columns"],
                config["values"],
                config.get("aggfunc", "sum"),
            )
        }

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        index = config["index"]
        index = one_or_list(index) if isinstance(index, list) else index
        return (
            f"{dst} = {src}.pivot_table(index={index!r}, columns={config['columns']!r}, "
            f"values={config['values']!r}, aggfunc={config.get('aggfunc', 'sum')!r})"
            f".reset_index()"
        )

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        index = config["index"]
        index = one_or_list(index) if isinstance(index, list) else index
        aggfunc = config.get("aggfunc", "sum")
        agg = "len" if aggfunc == "count" else aggfunc
        return (
            f"{dst} = {src}.pivot(on={config['columns']!r}, index={index!r}, "
            f"values={config['values']!r}, aggregate_function={agg!r})"
        )


class ExplodeRowsTransformation(BaseTransformation):
    """Split a column into multiple rows. With a delimiter, the text is split first
    (``"a,b"`` -> two rows); without one, an existing list column is exploded."""

    type = "explodeRows"
    # Both forms are pure expressions (str.split + explode / explode), so the
    # emitted code runs on a LazyFrame unchanged — no materialization needed.

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("explodeRows requires a 'column'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        delimiter = config.get("delimiter") or None
        return {"out": engine.explode_rows(inputs["in"], config["column"], delimiter)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        delimiter = config.get("delimiter") or None
        if delimiter:
            split = f"lambda _d: _d[{col!r}].astype('string').str.split({delimiter!r})"
            return f"{dst} = {src}.assign({pd_assign_args({col: split})}).explode({col!r}).reset_index(drop=True)"
        return f"{dst} = {src}.explode({col!r}).reset_index(drop=True)"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        delimiter = config.get("delimiter") or None
        if delimiter:
            return (
                f"{dst} = {src}.with_columns(pl.col({col!r}).cast(pl.Utf8).str.split({delimiter!r})).explode({col!r})"
            )
        return f"{dst} = {src}.explode({col!r})"


class DateDifferenceTransformation(BaseTransformation):
    """Compute the difference between two date columns (end - start) in a chosen unit
    (days, hours, minutes, seconds, weeks), as a new numeric column."""

    type = "dateDifference"
    _UNITS = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400, "weeks": 604800}

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("start_column"):
            raise ValueError("dateDifference requires a 'start_column'")
        if not config.get("end_column"):
            raise ValueError("dateDifference requires an 'end_column'")
        unit = config.get("unit", "days")
        if unit not in self._UNITS:
            raise ValueError(f"dateDifference 'unit' must be one of {sorted(self._UNITS)}")
        if not config.get("new_column"):
            raise ValueError("dateDifference requires a 'new_column' name")

    def _args(self, config: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            config["start_column"],
            config["end_column"],
            config.get("unit", "days"),
            config["new_column"],
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        start, end, unit, new = self._args(config)
        return {"out": engine.date_difference(inputs["in"], start, end, unit, new)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        start, end, unit, new = self._args(config)
        factor = self._UNITS[unit]
        diff = (
            f"lambda _d: (pd.to_datetime(_d[{end!r}], errors='coerce') - "
            f"pd.to_datetime(_d[{start!r}], errors='coerce')).dt.total_seconds() / {factor!r}"
        )
        return f"{dst} = {src}.assign({pd_assign_args({new: diff})})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        start, end, unit, new = self._args(config)
        factor = self._UNITS[unit]
        # str columns are parsed; already-temporal columns are cast — the input
        # dtype depends on upstream nodes, so dispatch on the schema at runtime.
        # Non-strict so bad values become null instead of raising.
        return (
            f"_sch = {src}.collect_schema()\n"
            f"_start = {polars_to_datetime_expr('_sch', repr(start))}\n"
            f"_end = {polars_to_datetime_expr('_sch', repr(end))}\n"
            f"{dst} = {src}.with_columns(((_end - _start).dt.total_seconds() / {factor!r}).alias({new!r}))"
        )
