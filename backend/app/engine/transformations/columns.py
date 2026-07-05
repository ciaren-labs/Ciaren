# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import (
    BaseTransformation,
    pd_assign_args,
    pl_exprs_arg,
    polars_to_datetime_expr,
)


class DropColumnsTransformation(BaseTransformation):
    type = "dropColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("dropColumns requires a non-empty 'columns' list")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.drop_columns(inputs["in"], config["columns"])}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.drop(columns={config['columns']!r})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.drop({config['columns']!r})"


class RenameColumnsTransformation(BaseTransformation):
    type = "renameColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("mapping") or not isinstance(config["mapping"], dict):
            raise ValueError("renameColumns requires a non-empty 'mapping' dict")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.rename_columns(inputs["in"], config["mapping"])}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.rename(columns={config['mapping']!r})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.rename({config['mapping']!r})"


class SelectColumnsTransformation(BaseTransformation):
    type = "selectColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("selectColumns requires a non-empty 'columns' list")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.select_columns(inputs["in"], config["columns"])}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}[{config['columns']!r}]"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.select({config['columns']!r})"


class CombineColumnsTransformation(BaseTransformation):
    """Join several columns into one text column with a separator (inverse of Split
    Column). Null cells become empty strings, so the separator is preserved."""

    type = "combineColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        columns = config.get("columns")
        if not isinstance(columns, list) or len(columns) < 2:
            raise ValueError("combineColumns requires a 'columns' list with at least two columns")
        if not config.get("new_column"):
            raise ValueError("combineColumns requires a 'new_column' name")

    def _args(self, config: dict[str, Any]) -> tuple[list[str], str, str, bool]:
        return (
            config["columns"],
            config["new_column"],
            config.get("separator", " "),
            bool(config.get("keep_original", True)),
        )

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        columns, new_column, separator, keep_original = self._args(config)
        return {"out": engine.combine_columns(inputs["in"], columns, new_column, separator, keep_original)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns, new_column, separator, keep_original = self._args(config)
        # Plain string concatenation instead of apply(sep.join, axis=1): same
        # result (each part is stringified and null-filled first), reads better,
        # and the lambda keeps the statement chainable.
        joiner = f" + {separator!r} + " if separator else " + "
        parts = joiner.join(f"_d[{c!r}].astype('string').fillna('')" for c in columns)
        line = f"{dst} = {src}.assign({pd_assign_args({new_column: f'lambda _d: {parts}'})})"
        if not keep_original:
            drop = [c for c in columns if c != new_column]
            line += f"\n{dst} = {dst}.drop(columns={drop!r})"
        return line

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns, new_column, separator, keep_original = self._args(config)
        parts = ", ".join(f"pl.col({c!r}).cast(pl.Utf8).fill_null('')" for c in columns)
        line = f"{dst} = {src}.with_columns(pl.concat_str([{parts}], separator={separator!r}).alias({new_column!r}))"
        if not keep_original:
            drop = [c for c in columns if c != new_column]
            line += f"\n{dst} = {dst}.drop({drop!r})"
        return line


class CoalesceColumnsTransformation(BaseTransformation):
    """Take the first non-null value across several columns into a new column."""

    type = "coalesceColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        columns = config.get("columns")
        if not isinstance(columns, list) or len(columns) < 2:
            raise ValueError("coalesceColumns requires a 'columns' list with at least two columns")
        if not config.get("new_column"):
            raise ValueError("coalesceColumns requires a 'new_column' name")

    def _args(self, config: dict[str, Any]) -> tuple[list[str], str, bool]:
        return (config["columns"], config["new_column"], bool(config.get("keep_original", True)))

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        columns, new_column, keep_original = self._args(config)
        return {"out": engine.coalesce_columns(inputs["in"], columns, new_column, keep_original)}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns, new_column, keep_original = self._args(config)
        # Chained where(pd.notna, ...) keeps first-non-null semantics like the
        # engine; fillna would try a silent downcast on object-dtype results
        # (deprecated, FutureWarning), which where() never does.
        expr = f"_d[{columns[0]!r}]" + "".join(f".where(pd.notna, _d[{c!r}])" for c in columns[1:])
        line = f"{dst} = {src}.assign({pd_assign_args({new_column: f'lambda _d: {expr}'})})"
        if not keep_original:
            drop = [c for c in columns if c != new_column]
            line += f"\n{dst} = {dst}.drop(columns={drop!r})"
        return line

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns, new_column, keep_original = self._args(config)
        parts = ", ".join(f"pl.col({c!r})" for c in columns)
        line = f"{dst} = {src}.with_columns(pl.coalesce([{parts}]).alias({new_column!r}))"
        if not keep_original:
            drop = [c for c in columns if c != new_column]
            line += f"\n{dst} = {dst}.drop({drop!r})"
        return line


class CastDtypesTransformation(BaseTransformation):
    type = "castDtypes"

    _VALID_DTYPES = {"integer", "float", "boolean", "string", "datetime"}
    _CODE_DTYPE = {
        "integer": "Int64",
        "float": "float64",
        "boolean": "boolean",
        "string": "string",
    }
    _POLARS_DTYPE = {
        "integer": "pl.Int64",
        "float": "pl.Float64",
        "boolean": "pl.Boolean",
        "string": "pl.Utf8",
    }

    def validate_config(self, config: dict[str, Any]) -> None:
        casts = config.get("casts")
        if not casts or not isinstance(casts, dict):
            raise ValueError("castDtypes requires a non-empty 'casts' dict {col: dtype}")
        invalid = set(casts.values()) - self._VALID_DTYPES
        if invalid:
            raise ValueError(f"castDtypes has unknown dtype(s): {sorted(invalid)}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        df = inputs["in"]
        fmt = config.get("format") or None
        errors = config.get("errors", "raise")
        for column, dtype in config["casts"].items():
            df = engine.cast_column(df, column, dtype, fmt, errors)
        return {"out": df}

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        fmt = config.get("format") or None
        errors = config.get("errors", "raise")
        # Each cast only reads its own column, so all of them fit one assign —
        # lambdas so the statement chains cleanly.
        items: dict[Any, str] = {}
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                extra = ""
                if fmt:
                    extra += f", format={fmt!r}"
                if errors != "raise":  # pandas' own default
                    extra += f", errors={errors!r}"
                items[column] = f"lambda _d: pd.to_datetime(_d[{column!r}]{extra})"
            elif dtype in ("integer", "float") and errors == "coerce":
                pd_dtype = self._CODE_DTYPE[dtype]
                items[column] = f"lambda _d: pd.to_numeric(_d[{column!r}], errors='coerce').astype({pd_dtype!r})"
            else:
                pd_dtype = self._CODE_DTYPE[dtype]
                items[column] = f"lambda _d: _d[{column!r}].astype({pd_dtype!r})"
        return f"{dst} = {src}.assign({pd_assign_args(items)})"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        fmt = config.get("format") or None
        strict = config.get("errors", "raise") != "coerce"
        exprs = []
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                exprs.append(polars_to_datetime_expr("_sch", repr(column), fmt=fmt, strict=strict))
            else:
                pl_dtype = self._POLARS_DTYPE[dtype]
                strict_arg = "" if strict else ", strict=False"  # strict is polars' default
                exprs.append(f"pl.col({column!r}).cast({pl_dtype}{strict_arg})")
        line = f"{dst} = {src}.with_columns({pl_exprs_arg(exprs)})"
        if any(dtype == "datetime" for dtype in config["casts"].values()):
            return f"_sch = {src}.collect_schema()\n{line}"
        return line
