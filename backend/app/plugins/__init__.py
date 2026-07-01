# SPDX-License-Identifier: AGPL-3.0-only
"""FlowFrame plugin runtime: built-in providers, the global ServiceRegistry, and
(Phase 1d) the external plugin loader.

The open core's own nodes/connectors/engines/exporters are registered here
as *built-in providers* — exactly the same mechanism a third-party plugin uses —
so the core has no privileged path. This package may import engine/connector
internals (it is app code); the pure contract lives in ``app.plugin_api``.
"""

from app.plugins.runtime import (
    build_registry,
    ensure_plugins_loaded,
    get_load_result,
    get_plugin_state,
    get_registry,
    reload_plugins,
    reset_registry,
)

__all__ = [
    "build_registry",
    "get_registry",
    "get_load_result",
    "ensure_plugins_loaded",
    "reset_registry",
    "reload_plugins",
    "get_plugin_state",
]
