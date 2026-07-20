"""The Validator plugin: contributes one executable node, ``validator.checkColumn``.

It demonstrates a practical data-quality check — the kind of thing a team builds
early when adopting a data platform. The node inspects a single column and adds a
boolean *pass/fail* column so downstream nodes (filters, reports) can act on the
result.

Two rules are built in:

* **regex** — every value in the column must match a regular expression
  (e.g. email addresses, SKU formats).
* **allowed_set** — every value must appear in a caller-supplied list.

The plugin depends only on the Ciaren plugin contract (``app.plugin_api``) and
pandas.  Ciaren bridges it to the active engine (polars/pandas) automatically.
"""

from __future__ import annotations

import re
from typing import Any

from app.plugin_api import (
    NodeProvider,
    NodeRuntime,
    NodeSpec,
    Plugin,
    PluginMetadata,
    PortSpec,
    ServiceRegistry,
)

PLUGIN_ID = "community.validator"
NODE_ID = "validator.checkColumn"

_VALID_RULES = ("regex", "allowed_set")


class _CheckColumnRuntime(NodeRuntime):
    """Validates a column and adds a boolean pass/fail column."""

    def validate_config(self, config: dict[str, Any]) -> None:
        column = config.get("column")
        if not column or not str(column).strip():
            raise ValueError("validator.checkColumn requires a 'column'.")

        rule = config.get("rule", "regex")
        if rule not in _VALID_RULES:
            raise ValueError(
                f"validator.checkColumn 'rule' must be one of {sorted(_VALID_RULES)}."
            )

        if rule == "regex":
            pattern = config.get("pattern", "")
            if not pattern:
                raise ValueError(
                    "validator.checkColumn 'regex' rule requires a 'pattern'."
                )
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(
                    f"validator.checkColumn: invalid regex {pattern!r} — {exc}"
                ) from exc

        elif rule == "allowed_set":
            allowed = config.get("allowed_values")
            if not isinstance(allowed, list) or not allowed:
                raise ValueError(
                    "validator.checkColumn 'allowed_set' rule requires "
                    "a non-empty 'allowed_values' list."
                )

    def execute(
        self, inputs: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        df = inputs["in"].copy()
        column = config["column"]
        rule = config.get("rule", "regex")
        out_col = config.get("output_column", "passed")

        if column not in df.columns:
            raise ValueError(
                f"validator.checkColumn: column {column!r} not found "
                f"in input (available: {list(df.columns)})."
            )

        series = df[column].astype(str)

        if rule == "regex":
            pattern = re.compile(config["pattern"])
            mask = series.str.match(pattern)
        else:  # allowed_set
            allowed = set(config["allowed_values"])
            mask = series.isin(allowed)

        df[out_col] = mask
        return {"out": df}

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        src, dst = input_vars["in"], output_vars["out"]
        column = config["column"]
        rule = config.get("rule", "regex")
        out_col = config.get("output_column", "passed")

        if rule == "regex":
            pattern = config["pattern"]
            return (
                f"{dst} = {src}.copy()\n"
                f"{dst}[{out_col!r}] = {src}[{column!r}]"
                f".astype(str).str.match({pattern!r})"
            )

        allowed = config["allowed_values"]
        return (
            f"{dst} = {src}.copy()\n"
            f"{dst}[{out_col!r}] = {src}[{column!r}]"
            f".isin({allowed!r})"
        )


class _ValidatorNodeProvider(NodeProvider):
    def nodes(self) -> list[NodeSpec]:
        return [
            NodeSpec(
                id=NODE_ID,
                label="Check Column",
                category="quality",
                description=(
                    "Example plugin node: validates a column's values against "
                    "a regex pattern or an allowed-value set and adds a boolean "
                    "pass/fail column."
                ),
                provider=PLUGIN_ID,
                version="0.1.0-alpha.1",
                inputs=(PortSpec(id="in"),),
                outputs=(PortSpec(id="out"),),
                default_config={
                    "column": "",
                    "rule": "regex",
                    "pattern": "",
                    "allowed_values": [],
                    "output_column": "passed",
                },
                capabilities=("node.validator",),
                config_schema={
                    "fields": [
                        {
                            "key": "column",
                            "label": "Column",
                            "type": "column",
                            "required": True,
                            "help": "The column to validate.",
                        },
                        {
                            "key": "rule",
                            "label": "Rule",
                            "type": "select",
                            "default": "regex",
                            "options": ("regex", "allowed_set"),
                            "help": "How to validate each value.",
                        },
                        {
                            "key": "pattern",
                            "label": "Regex pattern",
                            "type": "string",
                            "placeholder": "^[A-Z]{2}-\\d{4}$",
                            "help": "Every value must match this regular expression.",
                        },
                        {
                            "key": "allowed_values",
                            "label": "Allowed values",
                            "type": "string_list",
                            "help": "Every value must appear in this list.",
                        },
                        {
                            "key": "output_column",
                            "label": "Pass/fail column",
                            "type": "string",
                            "default": "passed",
                            "help": "Name of the boolean column to add (true = passed).",
                        },
                    ]
                },
            )
        ]

    def node_implementations(self) -> dict[str, Any]:
        return {NODE_ID: _CheckColumnRuntime()}


class ValidatorPlugin(Plugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id=PLUGIN_ID,
            name="Validator Plugin",
            version="0.1.0-alpha.1",
            publisher="community",
            description="Example plugin contributing a data-quality validation node.",
        )

    def register(self, registry: ServiceRegistry) -> None:
        registry.register_node_provider(_ValidatorNodeProvider())
