"""The process-wide :class:`ServiceRegistry` and how it is assembled.

``get_registry()`` lazily builds the registry by registering the built-in
providers (and, from Phase 1d, discovered external plugins). It is cached for the
life of the process; tests can ``reset_registry()`` to rebuild.
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

_registry: ServiceRegistry | None = None


def build_registry() -> ServiceRegistry:
    """Assemble a fresh registry from the built-in providers. External plugin
    discovery is wired in here in Phase 1d."""
    registry = ServiceRegistry()
    registry.register_node_provider(BuiltinNodeProvider())
    registry.register_connector_provider(BuiltinConnectorProvider())
    registry.register_storage_provider(BuiltinStorageProvider())
    registry.register_execution_provider(BuiltinExecutionProvider())
    registry.register_exporter_provider(BuiltinExporterProvider())
    registry.register_validator_provider(BuiltinValidatorProvider())
    return registry


def get_registry() -> ServiceRegistry:
    """The cached process-wide registry, built on first use."""
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def reset_registry() -> None:
    """Drop the cached registry so the next ``get_registry()`` rebuilds it. Used by
    tests that change what is installed/registered."""
    global _registry
    _registry = None
