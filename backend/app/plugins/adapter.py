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

from dataclasses import replace
from typing import Any

from app.engine.backends.base import AnyFrame, EngineBackend
from app.engine.preview_context import in_preview
from app.engine.transformations.base import BaseTransformation
from app.plugin_api import EMPTY_NODE_CONTEXT, NodeContext, NodeRuntime, NodeSpec, is_model_ref_frame


class PluginNodeExportError(ValueError):
    """Raised when exporting a flow that contains a plugin node which does not
    support code export (its runtime returned no ``to_python_code``)."""


class PluginTransformation(BaseTransformation):
    """Wraps a plugin :class:`NodeRuntime` as a :class:`BaseTransformation`.

    The runtime works on pandas, so ``execute`` converts the active engine's
    frames to pandas and back. Code export reuses the existing pandas→polars
    bridge: ``emits_pandas_code`` tells the polars generator to wrap this node's
    (pandas) code with ``to_pandas`` / ``from_pandas``.

    ``context`` carries the host services (granted permissions, ModelStore) the
    runtime receives via ``execute_with_context``; the default empty context keeps
    direct construction in tests working.
    """

    emits_pandas_code = True

    def __init__(self, spec: NodeSpec, runtime: NodeRuntime, context: NodeContext = EMPTY_NODE_CONTEXT) -> None:
        self.type = spec.id
        self._runtime = runtime
        self._context = context
        required = tuple(p.id for p in spec.inputs if p.required)
        self.input_handles = required or ("in",)
        self.optional_input_handles = tuple(p.id for p in spec.inputs if not p.required)
        self.multi_input = any(p.multi for p in spec.inputs)
        # Same defaulting as the node-kind registration: no declared outputs
        # means the single conventional "out" handle.
        self._declared_outputs = tuple(p.id for p in spec.outputs) or ("out",)
        self._model_outputs = frozenset(p.id for p in spec.outputs if p.type == "model")

    def validate_config(self, config: dict[str, Any]) -> None:
        self._runtime.validate_config(config)

    def execute(
        self,
        engine: EngineBackend,
        inputs: dict[str, AnyFrame],
        config: dict[str, Any],
    ) -> dict[str, AnyFrame]:
        pandas_inputs = {handle: engine.to_pandas(frame) for handle, frame in inputs.items()}
        # Stamp the live preview flag per call — the context is otherwise static
        # per plugin, but preview vs. run is decided at execution time.
        context = replace(self._context, in_preview=in_preview())
        result = self._runtime.execute_with_context(pandas_inputs, config, context)
        self._validate_outputs(result)
        return {handle: engine.from_pandas(frame) for handle, frame in result.items()}

    def _validate_outputs(self, result: Any) -> None:
        """Hold the runtime to its own NodeSpec: downstream nodes, the executor,
        and graph validation all plan around the declared handles, so a mismatch
        must fail here with a plugin-shaped message — not deep in the engine."""
        import pandas as pd

        if not isinstance(result, dict):
            raise ValueError(
                f"{self.type}: the plugin runtime must return a dict of output handle -> "
                f"pandas DataFrame, got {type(result).__name__}"
            )
        declared = set(self._declared_outputs)
        missing = sorted(declared - result.keys())
        unknown = sorted(result.keys() - declared)
        if missing or unknown:
            problems = []
            if missing:
                problems.append(f"missing declared output(s) {missing}")
            if unknown:
                problems.append(f"undeclared output(s) {unknown}")
            raise ValueError(
                f"{self.type}: the plugin runtime's outputs do not match its NodeSpec: "
                f"{'; '.join(problems)} (declared: {sorted(declared)})"
            )
        for handle, frame in result.items():
            if not isinstance(frame, pd.DataFrame):
                raise ValueError(
                    f"{self.type}: output {handle!r} must be a pandas DataFrame, got {type(frame).__name__}"
                )
            if handle in self._model_outputs and not is_model_ref_frame(frame):
                raise ValueError(
                    f'{self.type}: output {handle!r} is declared type="model" but does not carry '
                    "a model reference — emit ModelRef(...).to_frame() on model handles"
                )

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
