# SPDX-License-Identifier: AGPL-3.0-only
"""Flow parameters: typed, named values declared on a flow that node configs
reference via ``{{ name }}`` placeholders, resolved at run / preview / export time.

Parameter *specs* live on the graph document under a top-level ``parameters`` key
(a list of ``{name, type, default, description}`` dicts), so they travel with the
flow (export/import) and need no schema column — exactly like ``graph["engine"]``.

At run time the effective values are computed (declared defaults overlaid with
caller overrides), validated/coerced to their declared type, then substituted into
every node's ``data.config``. Substitution is **pure** (graph in, new graph out),
so the executor, graph validation and the code generators stay parameter-unaware —
they only ever see a fully-resolved graph.

Reference syntax inside a string config value:
- a value that is *exactly* ``{{ name }}`` is replaced with the **typed** value
  (an ``integer`` param stays an ``int`` so it can feed e.g. ``limitRows.n``);
- a placeholder embedded in a larger string (``data/{{ date }}.csv``) is string-
  interpolated with ``str(value)``;
- an unknown placeholder name is left untouched (never crash on literal braces).
"""

from __future__ import annotations

import copy
import keyword
import re
from typing import Any

from app.core.enums import ParameterType

# A reference embedded anywhere in a string, and the same anchored to the whole
# string (the latter triggers typed — not stringified — replacement).
_REF = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
_FULL_REF = re.compile(r"^\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$")
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Names that would collide with the exported scripts' own identifiers (a parameter
# becomes a top-level variable), producing broken or wrong Python. Python keywords
# would be a SyntaxError; the module aliases would shadow `import pandas as pd` etc.
_RESERVED_PARAM_NAMES = frozenset({"pd", "pl", "np", "os", "df"})


class ParameterError(ValueError):
    """A flow's parameter specs or a caller's overrides are invalid.

    Subclasses ``ValueError`` so callers that already map ``ValueError`` to a 400
    pick it up; services convert it explicitly to ``ValidationError``.
    """


def read_parameter_specs(graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The raw parameter spec list declared on a graph (``[]`` when none)."""
    if not isinstance(graph, dict):
        return []
    specs = graph.get("parameters")
    if specs is None:
        return []
    if not isinstance(specs, list):
        raise ParameterError("Flow 'parameters' must be a list of parameter definitions.")
    return specs


def validate_parameter_specs(graph: dict[str, Any] | None) -> None:
    """Validate a flow's parameter spec list without requiring values (save-time).

    Checks names, uniqueness and types, and that any declared default coerces to
    its type. Does *not* require every parameter to have a value (a parameter may
    be required and supplied only at run time). Raises :class:`ParameterError`.
    """
    by_name = _build_specs_by_name(read_parameter_specs(graph))
    for name, spec in by_name.items():
        if spec.get("default") is not None:
            _coerce(name, ParameterType(spec.get("type", ParameterType.STRING)), spec["default"])


def resolve_values(specs: list[dict[str, Any]], overrides: dict[str, Any]) -> dict[str, Any]:
    """Compute the effective, type-coerced value for every declared parameter.

    Overrides win over a spec's default; a parameter with neither is required.
    Unknown override keys (typos) and bad types raise :class:`ParameterError`.
    """
    specs_by_name = _build_specs_by_name(specs)

    unknown = set(overrides) - set(specs_by_name)
    if unknown:
        known = ", ".join(sorted(specs_by_name)) or "(none declared)"
        raise ParameterError(f"Unknown parameter override(s): {', '.join(sorted(unknown))}. Declared: {known}.")

    values: dict[str, Any] = {}
    for name, spec in specs_by_name.items():
        if name in overrides:
            raw = overrides[name]
        elif spec.get("default") is not None:
            raw = spec["default"]
        else:
            raise ParameterError(f"Parameter {name!r} has no value: pass an override or give it a default.")
        values[name] = _coerce(name, ParameterType(spec.get("type", ParameterType.STRING)), raw)
    return values


def substitute(obj: Any, values: dict[str, Any]) -> Any:
    """Recursively replace ``{{ name }}`` references in ``obj`` using ``values``."""
    if isinstance(obj, str):
        return _substitute_str(obj, values)
    if isinstance(obj, dict):
        return {k: substitute(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, values) for v in obj]
    return obj


def apply_parameters(
    graph: dict[str, Any], overrides: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a flow's parameters and return ``(resolved_graph, values)``.

    The returned graph is a deep copy with every node's ``data.config`` rewritten;
    the original is never mutated. When a flow declares no parameters and no
    overrides are given, the original graph is returned unchanged (no copy).
    """
    overrides = overrides or {}
    specs = read_parameter_specs(graph)
    if not specs:
        if overrides:
            # Overrides for a flow with no declared parameters is a caller error.
            raise ParameterError(
                f"This flow declares no parameters, but overrides were given: {', '.join(sorted(overrides))}."
            )
        return graph, {}

    values = resolve_values(specs, overrides)
    resolved = copy.deepcopy(graph)
    for node in resolved.get("nodes", []):
        data = node.get("data")
        if isinstance(data, dict) and isinstance(data.get("config"), dict):
            data["config"] = substitute(data["config"], values)
    return resolved, values


# -- internals ----------------------------------------------------------------


def _build_specs_by_name(specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate spec structure (name, uniqueness, type) and index by name."""
    specs_by_name: dict[str, dict[str, Any]] = {}
    for spec in specs:
        if not isinstance(spec, dict):
            raise ParameterError("Each flow parameter must be an object.")
        name = spec.get("name")
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise ParameterError(
                f"Invalid parameter name {name!r}: must start with a letter or underscore "
                "and contain only letters, digits and underscores."
            )
        if keyword.iskeyword(name) or keyword.issoftkeyword(name):
            raise ParameterError(f"Parameter name {name!r} is a Python keyword — choose another.")
        if name in _RESERVED_PARAM_NAMES:
            raise ParameterError(
                f"Parameter name {name!r} is reserved (it would clash with the exported code) — choose another."
            )
        if name in specs_by_name:
            raise ParameterError(f"Duplicate parameter name {name!r}.")
        type_ = spec.get("type", ParameterType.STRING)
        if type_ not in tuple(ParameterType):
            allowed = ", ".join(ParameterType)
            raise ParameterError(f"Parameter {name!r} has unknown type {type_!r} (allowed: {allowed}).")
        specs_by_name[name] = spec
    return specs_by_name


def _substitute_str(value: str, values: dict[str, Any]) -> Any:
    full = _FULL_REF.match(value)
    if full and full.group(1) in values:
        # Whole-string reference → preserve the value's declared (non-string) type.
        return values[full.group(1)]

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        return str(values[name]) if name in values else match.group(0)

    return _REF.sub(repl, value)


def _coerce(name: str, type_: ParameterType, raw: Any) -> Any:
    if type_ == ParameterType.STRING:
        return str(raw)
    if type_ == ParameterType.INTEGER:
        if isinstance(raw, bool):
            raise ParameterError(f"Parameter {name!r} must be an integer, got a boolean.")
        if isinstance(raw, float) and not raw.is_integer():
            raise ParameterError(f"Parameter {name!r} must be an integer, got {raw!r}.")
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ParameterError(f"Parameter {name!r} must be an integer, got {raw!r}.") from exc
    if type_ == ParameterType.NUMBER:
        if isinstance(raw, bool):
            raise ParameterError(f"Parameter {name!r} must be a number, got a boolean.")
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ParameterError(f"Parameter {name!r} must be a number, got {raw!r}.") from exc
    if type_ == ParameterType.BOOLEAN:
        if isinstance(raw, bool):
            return raw
        token = str(raw).strip().lower()
        if token in {"true", "1", "yes", "on"}:
            return True
        if token in {"false", "0", "no", "off"}:
            return False
        raise ParameterError(f"Parameter {name!r} must be a boolean, got {raw!r}.")
    raise ParameterError(f"Parameter {name!r} has unknown type {type_!r}.")  # pragma: no cover
