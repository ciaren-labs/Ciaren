from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation


class DropNullsTransformation(BaseTransformation):
    type = "dropNulls"

    def validate_config(self, config: dict[str, Any]) -> None:
        pass  # subset is optional

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        subset = config.get("subset") or None
        return {"out": engine.drop_nulls(inputs["in"], subset)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src = input_vars["in"]
        dst = output_vars["out"]
        subset = config.get("subset")
        if subset:
            return f"{dst} = {src}.dropna(subset={subset!r})"
        return f"{dst} = {src}.dropna()"


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

    def validate_config(self, config: dict[str, Any]) -> None:
        strategy = config.get("strategy", "constant")
        if strategy not in self._VALID_STRATEGIES:
            raise ValueError(
                f"fillNulls 'strategy' must be one of {sorted(self._VALID_STRATEGIES)}"
            )
        if strategy == "constant" and "value" not in config:
            raise ValueError("fillNulls with the 'constant' strategy requires a 'value'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        columns = config.get("columns") or None
        strategy = config.get("strategy", "constant")
        return {
            "out": engine.fill_nulls(inputs["in"], columns, strategy, config.get("value"))
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns = config.get("columns")
        strategy = config.get("strategy", "constant")

        if strategy == "constant":
            value = config.get("value")
            if columns:
                return (
                    f"{dst} = {src}.assign(**{{c: {src}[c].fillna({value!r}) "
                    f"for c in {columns!r}}})"
                )
            return f"{dst} = {src}.fillna({value!r})"

        cols = columns or "all columns"
        target = f"{columns!r}" if columns else f"{src}.columns"
        if strategy in ("ffill", "bfill"):
            method = strategy
            return (
                f"{dst} = {src}.assign(**{{c: {src}[c].{method}() "
                f"for c in {target}}})  # fill nulls ({cols})"
            )
        fill_expr = self._STRATEGY_FILL[strategy].format(s=src)
        return (
            f"{dst} = {src}.assign(**{{c: {src}[c].fillna({fill_expr}) "
            f"for c in {target}}})  # {strategy} fill ({cols})"
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

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.drop(columns={config['columns']!r})"


class RenameColumnsTransformation(BaseTransformation):
    type = "renameColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("mapping") or not isinstance(config["mapping"], dict):
            raise ValueError("renameColumns requires a non-empty 'mapping' dict")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.rename_columns(inputs["in"], config["mapping"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.rename(columns={config['mapping']!r})"


class SelectColumnsTransformation(BaseTransformation):
    type = "selectColumns"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("selectColumns requires a non-empty 'columns' list")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.select_columns(inputs["in"], config["columns"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}[{config['columns']!r}]"


class RemoveDuplicatesTransformation(BaseTransformation):
    type = "removeDuplicates"

    def validate_config(self, config: dict[str, Any]) -> None:
        keep = config.get("keep", "first")
        if keep not in ("first", "last", False):
            raise ValueError("removeDuplicates 'keep' must be 'first', 'last', or false")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        subset = config.get("subset") or None
        keep = config.get("keep", "first")
        return {"out": engine.drop_duplicates(inputs["in"], subset, keep)}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        subset = config.get("subset")
        keep = config.get("keep", "first")
        args = f"keep={keep!r}"
        if subset:
            args = f"subset={subset!r}, {args}"
        return f"{dst} = {src}.drop_duplicates({args})"


class FilterRowsTransformation(BaseTransformation):
    type = "filterRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        required = {"column", "operator"}
        if not required.issubset(config):
            raise ValueError(f"filterRows requires keys: {required}")
        op = config["operator"]
        # value is not required for unary operators (isnull/notnull)
        if op not in {"isnull", "notnull"} and "value" not in config:
            raise ValueError("filterRows requires a 'value' for this operator")
        if op == "between" and "value2" not in config:
            raise ValueError("filterRows 'between' requires a 'value2' (upper bound)")

    def _values(self, config: dict[str, Any]) -> Any:
        """Normalize the config value(s) into what the engine expects per operator."""
        op = config["operator"]
        val = config.get("value")
        if op == "between":
            return [val, config.get("value2")]
        if op == "in":
            if isinstance(val, list):
                return val
            return [v.strip() for v in str(val).split(",") if v.strip()]
        return val

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        col = config["column"]
        op = config["operator"]
        return {"out": engine.filter_rows(inputs["in"], col, op, self._values(config))}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, op = config["column"], config["operator"]
        val = config.get("value")
        _SIMPLE = {"==", "!=", ">", ">=", "<", "<="}
        if op in _SIMPLE:
            return f"{dst} = {src}[{src}[{col!r}] {op} {val!r}]"
        if op == "isnull":
            return f"{dst} = {src}[{src}[{col!r}].isna()]"
        if op == "notnull":
            return f"{dst} = {src}[{src}[{col!r}].notna()]"
        if op == "between":
            low, high = self._values(config)
            return f"{dst} = {src}[{src}[{col!r}].between({low!r}, {high!r})]"
        if op == "in":
            return f"{dst} = {src}[{src}[{col!r}].isin({self._values(config)!r})]"
        if op in {"contains", "startswith", "endswith"}:
            return f"{dst} = {src}[{src}[{col!r}].astype(str).str.{op}({val!r})]"
        raise ValueError(f"Unknown filter operator: {op!r}")


class CastDtypesTransformation(BaseTransformation):
    type = "castDtypes"

    _VALID_DTYPES = {"integer", "float", "boolean", "string", "datetime"}
    _CODE_DTYPE = {
        "integer": "Int64",
        "float": "float64",
        "boolean": "boolean",
        "string": "string",
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
        for column, dtype in config["casts"].items():
            df = engine.cast_column(df, column, dtype)
        return {"out": df}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        lines = [f"{dst} = {src}"]
        for column, dtype in config["casts"].items():
            if dtype == "datetime":
                lines.append(
                    f"{dst} = {dst}.assign(**{{{column!r}: "
                    f"pd.to_datetime({dst}[{column!r}])}})"
                )
            else:
                pd_dtype = self._CODE_DTYPE[dtype]
                lines.append(
                    f"{dst} = {dst}.assign(**{{{column!r}: "
                    f"{dst}[{column!r}].astype({pd_dtype!r})}})"
                )
        return "\n".join(lines)


class SortRowsTransformation(BaseTransformation):
    type = "sortRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("sortRows requires a non-empty 'columns' list")

    def _ascending(self, config: dict[str, Any]) -> list[bool]:
        columns = config["columns"]
        ascending = config.get("ascending", True)
        if isinstance(ascending, bool):
            return [ascending] * len(columns)
        return list(ascending)

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.sort_rows(
                inputs["in"], config["columns"], self._ascending(config)
            )
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        ascending = config.get("ascending", True)
        return (
            f"{dst} = {src}.sort_values(by={config['columns']!r}, "
            f"ascending={ascending!r})"
        )


class LimitRowsTransformation(BaseTransformation):
    type = "limitRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        n = config.get("n")
        if not isinstance(n, int) or n < 0:
            raise ValueError("limitRows requires a non-negative integer 'n'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.limit_rows(inputs["in"], config["n"])}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        return f"{dst} = {src}.head({config['n']!r})"


class ReplaceValuesTransformation(BaseTransformation):
    type = "replaceValues"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("replaceValues requires a 'column'")
        if "to_replace" not in config or "value" not in config:
            raise ValueError("replaceValues requires 'to_replace' and 'value'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.replace_values(
            inputs["in"], config["column"], config["to_replace"], config["value"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        return (
            f"{dst} = {src}.assign(**{{{col!r}: {src}[{col!r}]"
            f".replace({config['to_replace']!r}, {config['value']!r})}})"
        )


class StringTransformTransformation(BaseTransformation):
    type = "stringTransform"

    _VALID_OPS = {"lower", "upper", "strip", "title", "capitalize"}
    _CODE_OP = {
        "lower": "lower",
        "upper": "upper",
        "strip": "strip",
        "title": "title",
        "capitalize": "capitalize",
    }

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("column"):
            raise ValueError("stringTransform requires a 'column'")
        if config.get("operation") not in self._VALID_OPS:
            raise ValueError(f"stringTransform 'operation' must be one of {self._VALID_OPS}")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        result = engine.string_transform(
            inputs["in"], config["column"], config["operation"]
        )
        return {"out": result}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col = config["column"]
        method = self._CODE_OP[config["operation"]]
        return (
            f"{dst} = {src}.assign(**{{{col!r}: "
            f"{src}[{col!r}].astype('string').str.{method}()}})"
        )
