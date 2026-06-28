"""The process-wide :class:`ServiceRegistry` and how it is assembled.

``build_registry()`` returns the core built-ins only (deterministic, used by
tests). ``get_registry()`` additionally discovers external plugins and caches the
result for the life of the process; tests can ``reset_registry()`` to rebuild.
"""

from __future__ import annotations

from app.plugin_api import ServiceRegistry
from app.plugins.builtin import (
    BuiltinConnectorProvider,
    BuiltinExecutionProvider,
    BuiltinExporterProvider,
    BuiltinNodeProvider,
    BuiltinStorageProvider,
    BuiltinValidatorProvider,
)
from app.plugins.loader import LoadResult, default_plugin_dirs, load_plugins

_registry: ServiceRegistry | None = None
_load_result: LoadResult | None = None


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


def get_registry() -> ServiceRegistry:
    """The cached process-wide registry — built-ins plus discovered plugins."""
    global _registry, _load_result
    if _registry is None:
        registry = build_registry()
        _load_result = load_plugins(registry, plugin_dirs=default_plugin_dirs())
        _registry = registry
    return _registry


def get_load_result() -> LoadResult:
    """Diagnostics from the last plugin discovery (loaded plugins + isolated errors)."""
    get_registry()  # ensure discovery has run
    assert _load_result is not None
    return _load_result


def reset_registry() -> None:
    """Drop the cached registry + diagnostics so the next access rebuilds. Used by
    tests that change what is installed/registered."""
    global _registry, _load_result
    _registry = None
    _load_result = None
