"""Conditional column node: CASE-WHEN-style if/elif/else rules that compute a new
column. The first matching rule wins; unmatched rows take the default."""

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation

# Comparison operators (and aliases) that map straight to a Python/expr operator.
_COMPARISON = {
    "==": "==", "eq": "==",
    "!=": "!=", "ne": "!=",
    ">": ">", "gt": ">",
    ">=": ">=", "gte": ">=",
    "<": "<", "lt": "<",
    "<=": "<=", "lte": "<=",
}
_VALUELESS = {"isnull", "notnull"}
_OPERATORS = set(_COMPARISON) | _VALUELESS | {"contains", "startswith", "endswith"}


class ConditionalColumnTransformation(BaseTransformation):
    """Build a column from ordered ``rules`` ({column, operator, value, result})
    plus a ``default`` for rows that match none."""

    type = "conditionalColumn"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("new_column"):
            raise ValueError("conditionalColumn requires a 'new_column' name")
        rules = config.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("conditionalColumn requires a non-empty 'rules' list")
        for rule in rules:
            if not rule.get("column"):
                raise ValueError("each conditionalColumn rule needs a 'column'")
            operator = rule.get("operator", "==")
            if operator not in _OPERATORS:
                raise ValueError(f"conditionalColumn rule operator must be in {sorted(_OPERATORS)}")
            if operator not in _VALUELESS and "value" not in rule:
                raise ValueError(f"conditionalColumn rule '{operator}' needs a 'value'")

    def execute(
        self, engine: EngineBackend, inputs: dict[str, AnyFrame], config: dict[str, Any]
    ) -> dict[str, AnyFrame]:
        return {
            "out": engine.conditional_column(
                inputs["in"],
                config["rules"],
                config.get("default"),
                config["new_column"],
            )
        }

    # -- codegen --------------------------------------------------------

    @staticmethod
    def _pandas_mask(dst: str, rule: dict[str, Any]) -> str:
        col = f"{dst}[{rule['column']!r}]"
        op = rule.get("operator", "==")
        val = rule.get("value")
        if op in _COMPARISON:
            return f"{col} {_COMPARISON[op]} {val!r}"
        if op == "contains":
            return f"{col}.astype(str).str.contains({str(val)!r}, na=False)"
        if op == "startswith":
            return f"{col}.astype(str).str.startswith({str(val)!r}, na=False)"
        if op == "endswith":
            return f"{col}.astype(str).str.endswith({str(val)!r}, na=False)"
        return f"{col}.isna()" if op == "isnull" else f"{col}.notna()"

    def to_python_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        new = config["new_column"]
        lines = [f"{dst} = {src}.copy()", f"{dst}[{new!r}] = {config.get('default')!r}"]
        # Apply in reverse so the first matching rule wins on overlaps.
        for rule in reversed(config["rules"]):
            mask = self._pandas_mask(dst, rule)
            lines.append(f"{dst}.loc[{mask}, {new!r}] = {rule.get('result')!r}")
        return "\n".join(lines)

    @staticmethod
    def _polars_cond(rule: dict[str, Any]) -> str:
        col = f"pl.col({rule['column']!r})"
        op = rule.get("operator", "==")
        val = rule.get("value")
        if op in _COMPARISON:
            return f"{col} {_COMPARISON[op]} {val!r}"
        if op == "contains":
            return f"{col}.cast(pl.Utf8).str.contains({str(val)!r}, literal=True)"
        if op == "startswith":
            return f"{col}.cast(pl.Utf8).str.starts_with({str(val)!r})"
        if op == "endswith":
            return f"{col}.cast(pl.Utf8).str.ends_with({str(val)!r})"
        return f"{col}.is_null()" if op == "isnull" else f"{col}.is_not_null()"

    def to_polars_code(
        self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        new = config["new_column"]
        chain = ""
        for rule in config["rules"]:
            chain += f".when({self._polars_cond(rule)}).then(pl.lit({rule.get('result')!r}))"
        expr = f"pl{chain}.otherwise(pl.lit({config.get('default')!r}))"
        return f"{dst} = {src}.with_columns({expr}.alias({new!r}))"
