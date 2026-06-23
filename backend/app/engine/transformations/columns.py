from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


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
        lines = [f"{dst} = {src}"]
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                extra = ""
                if fmt:
                    extra += f", format={fmt!r}"
                if errors != "raise":
                    extra += f", errors={errors!r}"
                lines.append(f"{dst} = {dst}.assign(**{{{column!r}: pd.to_datetime({dst}[{column!r}]{extra})}})")
            elif dtype in ("integer", "float") and errors == "coerce":
                pd_dtype = self._CODE_DTYPE[dtype]
                lines.append(
                    f"{dst} = {dst}.assign(**{{{column!r}: "
                    f"pd.to_numeric({dst}[{column!r}], errors='coerce').astype({pd_dtype!r})}})"
                )
            else:
                pd_dtype = self._CODE_DTYPE[dtype]
                lines.append(f"{dst} = {dst}.assign(**{{{column!r}: {dst}[{column!r}].astype({pd_dtype!r})}})")
        return "\n".join(lines)

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        fmt = config.get("format") or None
        strict = config.get("errors", "raise") != "coerce"
        lines = [f"{dst} = {src}"]
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                lines.append(
                    f"{dst} = {dst}.with_columns(pl.col({column!r}).str.to_datetime(format={fmt!r}, strict={strict}))"
                )
            else:
                pl_dtype = self._POLARS_DTYPE[dtype]
                lines.append(f"{dst} = {dst}.with_columns(pl.col({column!r}).cast({pl_dtype}, strict={strict}))")
        return "\n".join(lines)
