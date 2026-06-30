# SPDX-License-Identifier: AGPL-3.0-only
"""Conditional column node: CASE-WHEN-style if/elif/else rules that compute a new
column. The first matching rule wins; unmatched rows take the default."""

from typing import Any

from app.engine.backends.base import (
    AnyFrame,
    EngineBackend,
    rule_combine_all,
    rule_conditions,
)
from app.engine.transformations.base import BaseTransformation

# Comparison operators (and aliases) that map straight to a Python/expr operator.
_COMPARISON = {
    "==": "==",
    "eq": "==",
    "!=": "!=",
    "ne": "!=",
    ">": ">",
    "gt": ">",
    ">=": ">=",
    "gte": ">=",
    "<": "<",
    "lt": "<",
    "<=": "<=",
    "lte": "<=",
}
_VALUELESS = {"isnull", "notnull"}
_OPERATORS = set(_COMPARISON) | _VALUELESS | {"contains", "startswith", "endswith"}


class ConditionalColumnTransformation(BaseTransformation):
    """Build a column from ordered ``rules`` plus a ``default`` for rows matching
    none. A rule has a ``result`` and one or more ``conditions``
    ({column, operator, value}) combined by ``match`` ("all" = AND, "any" = OR).
    A legacy flat rule ({column, operator, value, result}) is one condition."""

    type = "conditionalColumn"

    def validate_config(self, config: dict[str, Any]) -> None:
        if not config.get("new_column"):
            raise ValueError("conditionalColumn requires a 'new_column' name")
        rules = config.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("conditionalColumn requires a non-empty 'rules' list")
        for rule in rules:
            match = rule.get("match", "all")
            if match not in ("all", "any"):
                raise ValueError("conditionalColumn rule 'match' must be 'all' or 'any'")
            conditions = rule_conditions(rule)
            for condition in conditions:
                if not condition.get("column"):
                    raise ValueError("each conditionalColumn condition needs a 'column'")
                operator = condition.get("operator", "==")
                if operator not in _OPERATORS:
                    raise ValueError(f"conditionalColumn condition operator must be in {sorted(_OPERATORS)}")
                if operator not in _VALUELESS and "value" not in condition:
                    raise ValueError(f"conditionalColumn condition '{operator}' needs a 'value'")

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
        masks = [ConditionalColumnTransformation._pandas_condition(dst, c) for c in rule_conditions(rule)]
        if len(masks) == 1:
            return masks[0]
        joiner = " & " if rule_combine_all(rule) else " | "
        return joiner.join(f"({m})" for m in masks)

    @staticmethod
    def _pandas_condition(dst: str, condition: dict[str, Any]) -> str:
        col = f"{dst}[{condition['column']!r}]"
        op = condition.get("operator", "==")
        val = condition.get("value")
        if op in _COMPARISON:
            return f"{col} {_COMPARISON[op]} {val!r}"
        if op == "contains":
            return f"{col}.astype(str).str.contains({str(val)!r}, na=False)"
        if op == "startswith":
            return f"{col}.astype(str).str.startswith({str(val)!r}, na=False)"
        if op == "endswith":
            return f"{col}.astype(str).str.endswith({str(val)!r}, na=False)"
        return f"{col}.isna()" if op == "isnull" else f"{col}.notna()"

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
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
        exprs = [ConditionalColumnTransformation._polars_condition(c) for c in rule_conditions(rule)]
        if len(exprs) == 1:
            return exprs[0]
        joiner = " & " if rule_combine_all(rule) else " | "
        return joiner.join(f"({e})" for e in exprs)

    @staticmethod
    def _polars_condition(condition: dict[str, Any]) -> str:
        col = f"pl.col({condition['column']!r})"
        op = condition.get("operator", "==")
        val = condition.get("value")
        if op in _COMPARISON:
            return f"{col} {_COMPARISON[op]} {val!r}"
        if op == "contains":
            return f"{col}.cast(pl.Utf8).str.contains({str(val)!r}, literal=True)"
        if op == "startswith":
            return f"{col}.cast(pl.Utf8).str.starts_with({str(val)!r})"
        if op == "endswith":
            return f"{col}.cast(pl.Utf8).str.ends_with({str(val)!r})"
        return f"{col}.is_null()" if op == "isnull" else f"{col}.is_not_null()"

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        new = config["new_column"]
        chain = ""
        for rule in config["rules"]:
            chain += f".when({self._polars_cond(rule)}).then(pl.lit({rule.get('result')!r}))"
        expr = f"pl{chain}.otherwise(pl.lit({config.get('default')!r}))"
        return f"{dst} = {src}.with_columns({expr}.alias({new!r}))"
