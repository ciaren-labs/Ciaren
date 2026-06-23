from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation

_SIMPLE_OPS = {"==", "!=", ">", ">=", "<", "<="}


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
        if op in _SIMPLE_OPS:
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

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        col, op = config["column"], config["operator"]
        val = config.get("value")
        if op in _SIMPLE_OPS:
            return f"{dst} = {src}.filter(pl.col({col!r}) {op} {val!r})"
        if op == "isnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_null())"
        if op == "notnull":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_not_null())"
        if op == "between":
            return (
                f"{dst} = {src}.filter(pl.col({col!r})"
                f".is_between({val!r}, {config.get('value2')!r}))"
            )
        if op == "in":
            return f"{dst} = {src}.filter(pl.col({col!r}).is_in({self._values(config)!r}))"
        if op in {"contains", "startswith", "endswith"}:
            method = {
                "contains": "contains",
                "startswith": "starts_with",
                "endswith": "ends_with",
            }[op]
            return f"{dst} = {src}.filter(pl.col({col!r}).cast(pl.Utf8).str.{method}({val!r}))"
        raise ValueError(f"Unknown filter operator: {op!r}")


class SortRowsTransformation(BaseTransformation):
    type = "sortRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("columns"):
            raise ValueError("sortRows requires a non-empty 'columns' list")
        if config.get("na_position", "last") not in ("first", "last"):
            raise ValueError("sortRows 'na_position' must be 'first' or 'last'")

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
                inputs["in"],
                config["columns"],
                self._ascending(config),
                config.get("na_position", "last"),
            )
        }

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        ascending = config.get("ascending", True)
        na_position = config.get("na_position", "last")
        extra = f", na_position={na_position!r}" if na_position != "last" else ""
        return (
            f"{dst} = {src}.sort_values(by={config['columns']!r}, "
            f"ascending={ascending!r}{extra})"
        )

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        columns = config["columns"]
        ascending = config.get("ascending", True)
        descending = (
            [not a for a in ascending] if isinstance(ascending, list) else not ascending
        )
        nulls_last = config.get("na_position", "last") == "last"
        return (
            f"{dst} = {src}.sort({columns!r}, descending={descending!r}, "
            f"nulls_last={nulls_last!r})"
        )


class LimitRowsTransformation(BaseTransformation):
    type = "limitRows"

    def validate_config(self, config: dict[str, Any]) -> None:
        n = config.get("n")
        if not isinstance(n, int) or n < 0:
            raise ValueError("limitRows requires a non-negative integer 'n'")
        offset = config.get("offset", 0)
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("limitRows 'offset' must be a non-negative integer")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {"out": engine.limit_rows(inputs["in"], config["n"], config.get("offset", 0))}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        n, offset = config["n"], config.get("offset", 0)
        if offset:
            return f"{dst} = {src}.iloc[{offset!r}:{offset + n!r}]"
        return f"{dst} = {src}.head({n!r})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        n, offset = config["n"], config.get("offset", 0)
        if offset:
            return f"{dst} = {src}.slice({offset!r}, {n!r})"
        return f"{dst} = {src}.head({n!r})"


class SampleRowsTransformation(BaseTransformation):
    type = "sampleRows"
    polars_lazy_safe = False  # LazyFrame has no .sample()

    def validate_config(self, config: dict[str, Any]) -> None:
        n, frac = config.get("n"), config.get("frac")
        if frac is not None:
            if not isinstance(frac, (int, float)) or not (0 < frac <= 1):
                raise ValueError("sampleRows 'frac' must be a number in (0, 1]")
        elif not isinstance(n, int) or n < 0:
            raise ValueError("sampleRows requires a non-negative integer 'n' or a 'frac'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        frac = config.get("frac")
        n = None if frac is not None else config.get("n")
        return {"out": engine.sample_rows(inputs["in"], n, frac, config.get("seed"))}

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        seed = config.get("seed")
        size = (
            f"frac={config['frac']!r}"
            if config.get("frac") is not None
            else f"n={config['n']!r}"
        )
        return f"{dst} = {src}.sample({size}, random_state={seed!r})"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        seed = config.get("seed")
        size = (
            f"fraction={config['frac']!r}"
            if config.get("frac") is not None
            else f"n={config['n']!r}"
        )
        return f"{dst} = {src}.sample({size}, seed={seed!r})"


class RemoveDuplicatesTransformation(BaseTransformation):
    type = "removeDuplicates"

    _POLARS_KEEP = {"first": "first", "last": "last", False: "none"}

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

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        keep = self._POLARS_KEEP.get(config.get("keep", "first"), "first")
        subset = config.get("subset")
        args = f"keep={keep!r}, maintain_order=True"
        if subset:
            args = f"subset={subset!r}, {args}"
        return f"{dst} = {src}.unique({args})"
