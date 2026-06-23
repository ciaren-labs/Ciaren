from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


class GroupByAggregateTransformation(BaseTransformation):
    type = "groupByAggregate"

    # Aggregation name -> the polars Expr method that implements it.
    _POLARS_AGG = {
        "sum": "sum",
        "mean": "mean",
        "count": "count",
        "min": "min",
        "max": "max",
        "median": "median",
        "nunique": "n_unique",
    }

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("group_by"):
            raise ValueError("groupByAggregate requires 'group_by' list")
        if not config.get("aggregations"):
            raise ValueError("groupByAggregate requires 'aggregations' dict {col: func}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.groupby_agg(
            inputs["in"], config["group_by"], config["aggregations"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return (
            f"{dst} = {src}.groupby({config['group_by']!r})"
            f".agg({config['aggregations']!r}).reset_index()"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        by = config["group_by"]
        aggs = ", ".join(
            f"pl.col({col!r}).{self._POLARS_AGG.get(func, func)}().alias({col!r})"
            for col, func in config["aggregations"].items()
        )
        return f"{dst} = {src}.group_by({by!r}).agg([{aggs}])"


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

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        dst = output_vars["out"]
        src_list = list(input_vars.values())
        return f"{dst} = pd.concat([{', '.join(src_list)}], ignore_index=True)"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        dst = output_vars["out"]
        srcs = ", ".join(input_vars.values())
        return f"{dst} = pl.concat([{srcs}])"


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
        result = engine.add_column(
            inputs["in"], config["column_name"], config["expression"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column_name"]
        expr = config["expression"]
        return f"{dst} = {src}.assign(**{{{col!r}: {src}.eval({expr!r})}})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
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
        return {
            "out": engine.extract_date_parts(inputs["in"], config["column"], config["parts"])
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, parts = config["column"], config["parts"]
        items = ", ".join(f"{(col + '_' + p)!r}: _dt.dt.{p}" for p in parts)
        return f"_dt = pd.to_datetime({src}[{col!r}])\n{dst} = {src}.assign(**{{{items}}})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, parts = config["column"], config["parts"]
        # polars weekday is Monday=1..Sunday=7; subtract 1 to match pandas (Monday=0).
        exprs = ", ".join(
            f"(pl.col({col!r}).dt.weekday() - 1).alias({(col + '_' + p)!r})"
            if p == "weekday"
            else f"pl.col({col!r}).dt.{p}().alias({(col + '_' + p)!r})"
            for p in parts
        )
        return f"{dst} = {src}.with_columns([{exprs}])"


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

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        fmt = config.get("format") or None
        errors = config.get("errors", "coerce")
        return (
            f"{dst} = {src}.assign(**{{c: pd.to_datetime({src}[c], "
            f"format={fmt!r}, errors={errors!r}) for c in {cols!r}}})"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        cols = config["columns"]
        fmt = config.get("format") or None
        strict = config.get("errors", "coerce") != "coerce"
        return (
            f"{dst} = {src}.with_columns("
            f"[pl.col(c).str.to_datetime(format={fmt!r}, strict={strict!r}).alias(c) "
            f"for c in {cols!r}])"
        )


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

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return (
            f"{dst} = {src}.melt(id_vars={config['id_vars']!r}, "
            f"value_vars={config.get('value_vars') or None!r}, "
            f"var_name={config.get('var_name', 'variable')!r}, "
            f"value_name={config.get('value_name', 'value')!r})"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return (
            f"{dst} = {src}.unpivot(index={config['id_vars']!r}, "
            f"on={config.get('value_vars') or None!r}, "
            f"variable_name={config.get('var_name', 'variable')!r}, "
            f"value_name={config.get('value_name', 'value')!r})"
        )


class PivotTransformation(BaseTransformation):
    type = "pivot"

    def validate_config(self, config: dict[str, Any]) -> None:
        for key in ("index", "columns", "values"):
            if not config.get(key):
                raise ValueError(f"pivot requires '{key}'")

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

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        index = config["index"]
        index = [index] if isinstance(index, str) else index
        return (
            f"{dst} = {src}.pivot_table(index={index!r}, columns={config['columns']!r}, "
            f"values={config['values']!r}, aggfunc={config.get('aggfunc', 'sum')!r})"
            f".reset_index()"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        index = config["index"]
        index = [index] if isinstance(index, str) else index
        aggfunc = config.get("aggfunc", "sum")
        agg = "len" if aggfunc == "count" else aggfunc
        return (
            f"{dst} = {src}.pivot(on={config['columns']!r}, index={index!r}, "
            f"values={config['values']!r}, aggregate_function={agg!r})"
        )
