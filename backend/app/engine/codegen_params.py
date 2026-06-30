# SPDX-License-Identifier: AGPL-3.0-only
"""Render flow parameters as real variables in exported code.

The code generators format every config value through ``{value!r}``. To make a
parameterized config render as a *variable reference* rather than a literal, we
substitute ``{{ name }}`` placeholders with a :class:`CodeRef` whose ``repr`` is
the Python expression to emit:

- a whole-string ``{{ name }}`` → the bare variable name (``keep``), so the
  generated call reads ``df.head(keep)``;
- an embedded ``data/{{ date }}.csv`` → a ``str.format`` call
  (``'data/{}.csv'.format(date)``), which ``repr`` renders unquoted.

A ``# Flow parameters`` block defining each variable (= its default) is prepended
to the script body, so the exported code is runnable as-is and trivially tweaked.

This is best-effort: a node whose code generator does arithmetic on a config
value it can't handle will raise, and :class:`app.services.codegen_service` falls
back to inlining resolved defaults so export never fails.
"""

from __future__ import annotations

import copy
from typing import Any

from app.engine.parameters import _FULL_REF, _REF, read_parameter_specs, resolve_values


class CodeRef:
    """A config value that should render as raw Python source, not a literal.

    The code generators emit values via ``{value!r}``; ``CodeRef.__repr__`` returns
    the expression verbatim so e.g. ``df.head({n!r})`` becomes ``df.head(keep)``.
    Supports ``+`` so the handful of generators that compose offsets (e.g.
    ``offset + n``) still produce valid source.
    """

    __slots__ = ("expr",)

    def __init__(self, expr: str) -> None:
        self.expr = expr

    def __repr__(self) -> str:
        return self.expr

    def __add__(self, other: Any) -> "CodeRef":
        return CodeRef(f"{self.expr} + {_operand(other)}")

    def __radd__(self, other: Any) -> "CodeRef":
        return CodeRef(f"{_operand(other)} + {self.expr}")


def _operand(value: Any) -> str:
    """Render the right/left side of a ``CodeRef`` addition as source."""
    return value.expr if isinstance(value, CodeRef) else repr(value)


def parameter_block_lines(graph: dict[str, Any]) -> list[str]:
    """The ``name = default`` prelude documenting a flow's parameters (``[]`` if none)."""
    specs = read_parameter_specs(graph)
    if not specs:
        return []
    values = resolve_values(specs, {})
    lines = ["# Flow parameters — override these to re-run with different values."]
    for spec in specs:
        name = spec["name"]
        desc = spec.get("description")
        comment = f"  # {desc}" if desc else ""
        lines.append(f"{name} = {values[name]!r}{comment}")
    return lines


def substitute_for_codegen(graph: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy ``graph`` with every node config's ``{{ name }}`` reference turned
    into a :class:`CodeRef`. Configs of flows without parameters are untouched."""
    names = set(resolve_values(read_parameter_specs(graph), {}))
    if not names:
        return graph
    resolved = copy.deepcopy(graph)
    for node in resolved.get("nodes", []):
        data = node.get("data")
        if isinstance(data, dict) and isinstance(data.get("config"), dict):
            data["config"] = _to_coderefs(data["config"], names)
    return resolved


def _to_coderefs(obj: Any, names: set[str]) -> Any:
    if isinstance(obj, str):
        return _str_to_coderef(obj, names)
    if isinstance(obj, dict):
        return {k: _to_coderefs(v, names) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_coderefs(v, names) for v in obj]
    return obj


def _str_to_coderef(value: str, names: set[str]) -> Any:
    full = _FULL_REF.match(value)
    if full and full.group(1) in names:
        # Whole-string reference → bare variable (keeps the variable's runtime type).
        return CodeRef(full.group(1))

    template: list[str] = []
    args: list[str] = []
    last = 0
    for match in _REF.finditer(value):
        name = match.group(1)
        template.append(_escape_braces(value[last : match.start()]))
        if name in names:
            template.append("{}")
            args.append(name)
        else:
            template.append(_escape_braces(match.group(0)))
        last = match.end()
    if not args:
        return value  # no known references — leave the literal string as-is
    template.append(_escape_braces(value[last:]))
    return CodeRef(f"{''.join(template)!r}.format({', '.join(args)})")


def _escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")
