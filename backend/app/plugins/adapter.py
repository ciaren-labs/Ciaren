# SPDX-License-Identifier: AGPL-3.0-only
"""Adapt a plugin's :class:`NodeRuntime` to the engine's ``BaseTransformation``.

This is the bridge that makes a plugin-contributed node executable end-to-end:
once registered in the engine registry (see ``app.plugins.runtime``), the
executor, preview, graph validation, and both code generators treat it exactly
like a built-in node. Handle topology comes from the node's ``NodeSpec``; the
plugin's pandas runtime is bridged to the active engine via the backend's
``to_pandas`` / ``from_pandas``.
"""

from __future__ import annotations

from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.transformations.base import BaseTransformation
from app.plugin_api import NodeRuntime, NodeSpec


class PluginNodeExportError(ValueError):
    """Raised when exporting a flow that contains a plugin node which does not
    support code export (its runtime returned no ``to_python_code``)."""


class PluginTransformation(BaseTransformation):
    """Wraps a plugin :class:`NodeRuntime` as a :class:`BaseTransformation`.

    The runtime works on pandas, so ``execute`` converts the active engine's
    frames to pandas and back. Code export reuses the existing pandas→polars
    bridge: ``emits_pandas_code`` tells the polars generator to wrap this node's
    (pandas) code with ``to_pandas`` / ``from_pandas``.
    """

    emits_pandas_code = True

    def __init__(self, spec: NodeSpec, runtime: NodeRuntime) -> None:
        self.type = spec.id
        self._runtime = runtime
        required = tuple(p.id for p in spec.inputs if p.required)
        self.input_handles = required or ("in",)
        self.optional_input_handles = tuple(p.id for p in spec.inputs if not p.required)
        self.multi_input = any(p.multi for p in spec.inputs)

    def validate_config(self, config: dict[str, Any]) -> None:
        self._runtime.validate_config(config)

    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]:
        pandas_inputs = {handle: engine.to_pandas(frame) for handle, frame in inputs.items()}
        result = self._runtime.execute(pandas_inputs, config)
        return {handle: engine.from_pandas(frame) for handle, frame in result.items()}

    def imports(self, config: dict[str, Any]) -> list[str]:
        return list(self._runtime.imports(config))

    def to_python_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        code = self._runtime.to_python_code(input_vars, output_vars, config)
        if code is None:
            raise PluginNodeExportError(f"node {self.type!r} does not support code export (no to_python_code)")
        return code

    def to_polars_code(
        self,
        input_vars: dict[str, str],
        output_vars: dict[str, str],
        config: dict[str, Any],
    ) -> str:
        # emits_pandas_code=True → the polars generator bridges this pandas code.
        return self.to_python_code(input_vars, output_vars, config)
