"""The process-wide :class:`ServiceRegistry` and how it is assembled.

``build_registry()`` returns the core built-ins only (deterministic, used by
tests). ``get_registry()`` additionally discovers external plugins, **bridges**
their executable nodes into the engine registry (so they run end-to-end), and
caches the result for the life of the process; tests can ``reset_registry()`` to
rebuild and unregister the bridged nodes.
"""

from __future__ import annotations

import logging

from app.engine.registry import register_transformations, unregister_transformations
from app.plugin_api import NodeRuntime, ServiceRegistry
from app.plugins.adapter import PluginTransformation
from app.plugins.builtin import (
    BuiltinConnectorProvider,
    BuiltinExecutionProvider,
    BuiltinExporterProvider,
    BuiltinNodeProvider,
    BuiltinStorageProvider,
    BuiltinValidatorProvider,
)
from app.plugins.loader import LoadResult, default_plugin_dirs, load_plugins

logger = logging.getLogger("app.plugins.runtime")

_registry: ServiceRegistry | None = None
_load_result: LoadResult | None = None
#: Node types this process bridged into the engine registry, so reset can undo it.
_bridged_types: list[str] = []


def build_registry() -> ServiceRegistry:
    """Assemble a fresh registry from the built-in providers only."""
    registry = ServiceRegistry()
    registry.register_node_provider(BuiltinNodeProvider())
    registry.register_connector_provider(BuiltinConnectorProvider())
    registry.register_storage_provider(BuiltinStorageProvider())
    registry.register_execution_provider(BuiltinExecutionProvider())
    registry.register_exporter_provider(BuiltinExporterProvider())
    registry.register_validator_provider(BuiltinValidatorProvider())
    return registry


def _bridge_plugin_nodes(registry: ServiceRegistry) -> None:
    """Register a :class:`PluginTransformation` in the engine registry for every
    plugin node that ships an executable :class:`NodeRuntime`, so it runs and
    exports like a built-in. Catalog-only plugin nodes (no runtime) are left as
    pure catalog entries."""
    for spec in registry.node_specs():
        impl = registry.node_implementation(spec.id)
        if not isinstance(impl, NodeRuntime):
            continue
        try:
            register_transformations(PluginTransformation(spec, impl))
        except ValueError:
            # Already registered (e.g. duplicate) — skip; the catalog spec remains.
            logger.warning("Skipped bridging node %r: already registered", spec.id)
            continue
        _bridged_types.append(spec.id)


def get_registry() -> ServiceRegistry:
    """The cached process-wide registry — built-ins plus discovered plugins, with
    plugin nodes bridged into the engine so they execute."""
    global _registry, _load_result
    if _registry is None:
        registry = build_registry()
        _load_result = load_plugins(registry, plugin_dirs=default_plugin_dirs())
        _bridge_plugin_nodes(registry)
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
    assert _load_result is not None
    return _load_result


def reset_registry() -> None:
    """Drop the cached registry + diagnostics and unregister any bridged plugin
    nodes from the engine registry, so the next access rebuilds cleanly. Used by
    tests that change what is installed/registered."""
    global _registry, _load_result, _bridged_types
    if _bridged_types:
        unregister_transformations(*_bridged_types)
        _bridged_types = []
    _registry = None
    _load_result = None
