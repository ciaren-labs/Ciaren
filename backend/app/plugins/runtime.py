# SPDX-License-Identifier: AGPL-3.0-only
"""The process-wide :class:`ServiceRegistry` and how it is assembled.

``build_registry()`` returns the core built-ins only (deterministic, used by
tests). ``get_registry()`` additionally discovers external plugins, **bridges**
their executable nodes into the engine registry (so they run end-to-end), and
caches the result for the life of the process; tests can ``reset_registry()`` to
rebuild and unregister the bridged nodes.
"""

from __future__ import annotations

import logging
import threading

from app.engine import node_kinds
from app.engine.registry import register_transformations, unregister_transformations
from app.plugin_api import NodeContext, NodeRuntime, NodeSpec, ServiceRegistry
from app.plugins.adapter import PluginTransformation
from app.plugins.builtin import (
    BuiltinConnectorProvider,
    BuiltinExecutionProvider,
    BuiltinExporterProvider,
    BuiltinNodeProvider,
    BuiltinStorageProvider,
    BuiltinValidatorProvider,
    MlNodeProvider,
)
from app.plugins.loader import LoadResult, default_plugin_dirs, load_plugins
from app.plugins.state import PluginStateStore

logger = logging.getLogger("app.plugins.runtime")

_registry: ServiceRegistry | None = None
_load_result: LoadResult | None = None
#: Node types this process bridged into the engine registry, so reset can undo it.
_bridged_types: list[str] = []
#: Serializes registry build/reset. Runs execute on worker threads while the API
#: (enable/disable/grant) can trigger ``reload_plugins`` on the event loop; without
#: this two callers could build the registry concurrently and double-bridge plugin
#: nodes, or a reset could interleave with a build and corrupt ``_bridged_types``.
#: Re-entrant because ``get_load_result``/``reload_plugins`` call ``get_registry``
#: while already holding it.
_lock = threading.RLock()


def build_registry() -> ServiceRegistry:
    """Assemble a fresh registry from the built-in providers only.

    The ML node provider is registered only when the ``[ml]`` extra is importable,
    so the open-core ETL core does not depend on it — it plugs in exactly like a
    third-party provider would. ``ML_ENABLED`` still gates the *product surface*
    (catalog filtering, run guard) at the service layer.
    """
    from app.ml.availability import ml_core_available

    registry = ServiceRegistry()
    registry.register_node_provider(BuiltinNodeProvider())
    if ml_core_available():
        registry.register_node_provider(MlNodeProvider())
    registry.register_connector_provider(BuiltinConnectorProvider())
    registry.register_storage_provider(BuiltinStorageProvider())
    registry.register_execution_provider(BuiltinExecutionProvider())
    registry.register_exporter_provider(BuiltinExporterProvider())
    registry.register_validator_provider(BuiltinValidatorProvider())
    return registry


def _node_context_for(plugin_id: str, state: PluginStateStore) -> NodeContext:
    """Assemble the host services a plugin's runtimes receive: its *granted*
    permissions and (when the ML core is importable) a permission-gated
    MLflow-backed ModelStore."""
    from app.ml.availability import ml_core_available

    granted = frozenset(state.granted(plugin_id))
    models = None
    if ml_core_available():
        from app.plugins.model_store import MlflowModelStore

        models = MlflowModelStore(plugin_id, granted)
    return NodeContext(plugin_id=plugin_id, permissions=granted, models=models)


def _register_node_kind(spec: NodeSpec) -> None:
    """Teach the engine's node-kind tables this plugin node's handle topology, so
    model wires, multi-output edges, and flow-terminal behavior validate and
    execute exactly like a built-in's."""
    node_kinds.register_plugin_node_kind(
        spec.id,
        output_handles=tuple(p.id for p in spec.outputs) or ("out",),
        model_input_handles=frozenset(p.id for p in spec.inputs if p.type == "model"),
        model_output_handles=frozenset(p.id for p in spec.outputs if p.type == "model"),
        flow_terminal=spec.is_flow_terminal,
        model_sink=spec.is_model_sink,
    )


def _bridge_plugin_nodes(registry: ServiceRegistry, state: PluginStateStore) -> None:
    """Register a :class:`PluginTransformation` in the engine registry for every
    plugin node that ships an executable :class:`NodeRuntime`, so it runs and
    exports like a built-in. Catalog-only plugin nodes (no runtime) are left as
    pure catalog entries."""
    contexts: dict[str, NodeContext] = {}
    for spec in registry.node_specs():
        impl = registry.node_implementation(spec.id)
        if not isinstance(impl, NodeRuntime):
            continue
        if spec.provider not in contexts:
            contexts[spec.provider] = _node_context_for(spec.provider, state)
        try:
            register_transformations(PluginTransformation(spec, impl, contexts[spec.provider]))
        except ValueError:
            # Already registered (e.g. duplicate) — skip; the catalog spec remains.
            logger.warning("Skipped bridging node %r: already registered", spec.id)
            continue
        try:
            _register_node_kind(spec)
        except ValueError:
            logger.warning("Node %r shadows a built-in kind; skipping its kind registration", spec.id)
        _bridged_types.append(spec.id)


def get_registry() -> ServiceRegistry:
    """The cached process-wide registry — built-ins plus discovered plugins, with
    plugin nodes bridged into the engine so they execute."""
    global _registry, _load_result
    if _registry is not None:
        return _registry
    with _lock:
        # Re-check under the lock: another thread may have built it while we waited.
        if _registry is None:
            registry = build_registry()
            # License providers for the configured token issuers must exist before
            # any plugin is processed, or a license_required plugin could never
            # load (its own code — where a vendor provider would register — is
            # exactly what the license gate keeps un-imported).
            from app.plugins.licensing import core_license_providers

            for provider in core_license_providers():
                registry.register_license_provider(provider)
            state = PluginStateStore()
            _load_result = load_plugins(
                registry,
                plugin_dirs=default_plugin_dirs(),
                state=state,
            )
            _bridge_plugin_nodes(registry, state)
            _registry = registry
    return _registry


def ensure_plugins_loaded() -> None:
    """Idempotently build the registry + bridge plugin nodes. Best-effort: used as
    the process-pool worker initializer so plugin nodes execute in ``process``
    mode too. A plugin failure here must never break core execution."""
    try:
        get_registry()
    except Exception:  # noqa: BLE001 — worker init must not crash the pool
        logger.warning("Plugin bootstrap in worker failed; continuing without plugins.", exc_info=True)


def get_load_result() -> LoadResult:
    """Diagnostics from the last plugin discovery (loaded plugins + isolated errors)."""
    get_registry()  # ensure discovery has run
    with _lock:
        assert _load_result is not None
        return _load_result


def reset_registry() -> None:
    """Drop the cached registry + diagnostics and unregister any bridged plugin
    nodes from the engine registry, so the next access rebuilds cleanly. Used by
    tests that change what is installed/registered."""
    global _registry, _load_result, _bridged_types
    with _lock:
        if _bridged_types:
            unregister_transformations(*_bridged_types)
            node_kinds.unregister_plugin_node_kinds(*_bridged_types)
            _bridged_types = []
        _registry = None
        _load_result = None


def reload_plugins() -> LoadResult:
    """Rebuild the registry from scratch (re-reading plugin state from disk) and
    return the fresh load result. Called after the API changes enable/disable or
    permission grants so the change takes effect live, without a restart."""
    with _lock:  # reset + rebuild as one unit so no caller sees a half-reset state
        reset_registry()
        return get_load_result()


def get_plugin_state() -> PluginStateStore:
    """A freshly-read view of the persisted plugin state (enabled + grants)."""
    return PluginStateStore()
