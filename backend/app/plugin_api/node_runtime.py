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

from abc import ABC
from dataclasses import dataclass
from typing import Any, Protocol

from app.plugin_api.model_ref import ModelRef
from app.plugin_api.specs import Permission


class ModelStore(Protocol):
    """Host-provided model persistence, handed to runtimes via :class:`NodeContext`.

    This is *the* sanctioned way for a plugin train node to persist a model: log
    it as an MLflow artifact and pass the returned :class:`ModelRef` downstream —
    never a live estimator, and never a hand-rolled pickle on disk. Loading goes
    through the host's security checks (URI allowlist, artifact-root confinement,
    format allowlist) and is permission-gated: pickle-backed loads require the
    plugin to have been granted ``joblib_load`` / ``local_model_load``.
    """

    def log_sklearn_model(
        self,
        model: Any,
        *,
        model_type: str,
        task_type: str,
        target_column: str | None = None,
        feature_columns: tuple[str, ...] = (),
        params: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        input_example: Any = None,
        experiment: str | None = None,
        preprocessing: dict[str, Any] | None = None,
        seed: int | None = None,
        training_config: dict[str, Any] | None = None,
    ) -> ModelRef:
        """Persist a fitted sklearn-compatible model/pipeline to MLflow and return
        the reference to emit on a ``model`` output handle.

        The reference's ``model_config_json`` is part of the model-wire contract,
        not optional metadata: core consumers read it (Cross-Validate rebuilds the
        estimator from ``model_type`` + ``hyperparameters`` + ``preprocessing`` +
        ``seed``). Pass what you have — ``params`` become the recorded
        hyperparameters, and ``training_config`` entries overlay the generated
        config for anything beyond the named arguments."""
        ...

    def load_model(self, ref_or_uri: ModelRef | str) -> Any:
        """Load a model from a reference/URI after the host's security checks."""
        ...


@dataclass(frozen=True)
class NodeContext:
    """Host services available to a node while it executes.

    Passed to :meth:`NodeRuntime.execute_with_context`. ``permissions`` are the
    permissions the user actually **granted** the plugin (not what the manifest
    requested); ``models`` is ``None`` when the host has no ML/MLflow support
    installed, so a runtime must fail with a clear message rather than assume it.

    ``in_preview`` is True while the editor previews the node on sampled data:
    expensive/persistent work (training a model, writing anywhere) should be
    skipped, returning a cheap placeholder instead — exactly like the core train
    nodes do.
    """

    plugin_id: str = ""
    permissions: frozenset[Permission] = frozenset()
    models: ModelStore | None = None
    in_preview: bool = False


#: A context with no plugin identity, no grants, and no services — what a runtime
#: gets in contexts that predate/bypass the plugin loader (e.g. direct tests).
EMPTY_NODE_CONTEXT = NodeContext()


class NodeRuntime(ABC):
    """The runnable side of a plugin node.

    Handle conventions match the node's :class:`~app.plugin_api.specs.NodeSpec`:
    a single-input node reads ``inputs["in"]`` and returns ``{"out": frame}``.
    """

    def validate_config(self, config: dict[str, Any]) -> None:
        """Raise ``ValueError`` on invalid config. Default: accept anything."""

    def execute(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """Run the node. ``inputs`` maps input-handle -> pandas DataFrame; return a
        map of output-handle -> pandas DataFrame.

        Override this **or** :meth:`execute_with_context` (which supersedes it
        when a node needs host services)."""
        raise NotImplementedError(f"{type(self).__name__} implements neither execute nor execute_with_context")

    def execute_with_context(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: NodeContext,
    ) -> dict[str, Any]:
        """Run the node with host services (:class:`NodeContext`).

        Ciaren always calls this entry point; the default just delegates to
        :meth:`execute`, so existing runtimes keep working unchanged. Override it
        (instead of ``execute``) when the node needs context services — e.g. a
        train node persisting through ``context.models``.
        """
        return self.execute(inputs, config)

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
