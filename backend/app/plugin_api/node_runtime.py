# SPDX-License-Identifier: Apache-2.0
"""Executable behavior for a plugin-contributed node.

A :class:`NodeProvider` can hand Ciaren a :class:`NodeRuntime` for a node id
(via ``node_implementations``); Ciaren wraps it so the node runs in previews
and runs and exports to code, exactly like a built-in node.

The contract is **pandas-based and engine-agnostic**: a runtime receives and
returns pandas DataFrames keyed by handle, and Ciaren converts to/from the
active engine (polars/pandas) around the call. This keeps the contract free of
any Ciaren engine internals — a plugin depends only on ``app.plugin_api`` and
pandas (which it already uses as a data plugin). Frames are typed ``Any`` here so
the contract itself carries no hard pandas dependency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NodeRuntime(ABC):
    """The runnable side of a plugin node.

    Handle conventions match the node's :class:`~app.plugin_api.specs.NodeSpec`:
    a single-input node reads ``inputs["in"]`` and returns ``{"out": frame}``.
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """Raise ``ValueError`` on invalid config. Default: accept anything."""

    @abstractmethod
    def execute(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """Run the node. ``inputs`` maps input-handle -> pandas DataFrame; return a
        map of output-handle -> pandas DataFrame."""

    def imports(self, config: dict[str, Any]) -> list[str]:
        """Extra top-level import lines the exported pandas script needs."""
        return []

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str | None:
        """Readable **pandas** code for this node (``df`` variables), or ``None`` if
        the node cannot be exported. ``input_vars`` / ``output_vars`` map handles to
        the variable names to read/assign. Ciaren bridges this into a polars
        export automatically."""
        return None
