"""A tiny, dependency-free event bus so plugins extend behaviour without
modifying the core.

The bus lives on the :class:`~app.plugin_api.registry.ServiceRegistry` and is
handed to a plugin's ``register()``; the plugin subscribes callbacks to named
hooks. The core *emits* hooks at well-defined points (graph validation,
execution, export, plugin lifecycle). Emission is **error-isolated**: a buggy
subscriber is logged and skipped, never breaking a run.

This module is part of the stable contract package — it imports only the stdlib,
so a plugin can depend on it without pulling in the FlowFrame app or engine.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from enum import Enum

logger = logging.getLogger("app.plugin_api.events")


class Hook(str, Enum):
    """The lifecycle/execution points the core can emit. Values are the public
    hook names; subscribe with either the enum member or the raw string.

    **Emitted today** (a subscriber will be called): ``plugin_enabled``,
    ``plugin_disabled``, ``before_graph_execute``, ``after_graph_execute``,
    ``before_node_execute``, ``after_node_execute`` (the node hooks only in
    in-process ``thread`` execution mode — a process-pool worker can't reach
    parent-registered subscribers), and ``export_requested``.

    **Reserved** (defined for a stable contract but **not emitted yet**, so do not
    rely on them firing): ``plugin_installed`` (installation happens in the CLI, a
    separate process with no running bus), ``project_created`` / ``project_opened``
    / ``project_saved``, ``graph_loaded``, and ``graph_validated``. They are kept
    here so the hook namespace is stable when wiring lands.
    """

    # -- plugin lifecycle --
    plugin_installed = "on_plugin_installed"  # reserved (CLI-side install)
    plugin_enabled = "on_plugin_enabled"
    plugin_disabled = "on_plugin_disabled"

    # -- project / graph (reserved) --
    project_created = "on_project_created"
    project_opened = "on_project_opened"
    project_saved = "on_project_saved"
    graph_loaded = "on_graph_loaded"
    graph_validated = "on_graph_validated"

    # -- execution --
    before_graph_execute = "before_graph_execute"
    after_graph_execute = "after_graph_execute"
    before_node_execute = "before_node_execute"
    after_node_execute = "after_node_execute"

    # -- export --
    export_requested = "on_export_requested"


#: A hook subscriber. Called with the keyword payload the emitter provides; its
#: return value is ignored. Keep signatures permissive (``**kwargs``) so adding a
#: payload field later does not break existing subscribers.
HookCallback = Callable[..., None]


def _key(hook: Hook | str) -> str:
    return hook.value if isinstance(hook, Hook) else hook


class EventBus:
    """Synchronous, in-process pub/sub for :class:`Hook` points.

    Designed to be cheap when nothing is listening (the common case): :meth:`emit`
    is a single dict lookup that returns early with no subscribers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[HookCallback]] = defaultdict(list)

    def subscribe(self, hook: Hook | str, callback: HookCallback) -> None:
        """Register ``callback`` for ``hook``. The same callback is only added once."""
        bucket = self._subscribers[_key(hook)]
        if callback not in bucket:
            bucket.append(callback)

    def unsubscribe(self, hook: Hook | str, callback: HookCallback) -> None:
        """Remove ``callback`` from ``hook`` if present (no error if it isn't)."""
        bucket = self._subscribers.get(_key(hook))
        if bucket and callback in bucket:
            bucket.remove(callback)

    def subscriber_count(self, hook: Hook | str) -> int:
        return len(self._subscribers.get(_key(hook), ()))

    def emit(self, hook: Hook | str, **payload: object) -> None:
        """Notify every subscriber of ``hook`` with ``payload``.

        A subscriber that raises is logged and skipped — one bad plugin must
        never break execution. Subscribers are notified in registration order,
        over a snapshot so a subscriber may safely (un)subscribe during dispatch.
        """
        bucket = self._subscribers.get(_key(hook))
        if not bucket:
            return
        for callback in list(bucket):
            try:
                callback(**payload)
            except Exception:  # noqa: BLE001 — a plugin hook must not break core flow
                logger.warning("Hook subscriber for %r failed; continuing.", _key(hook), exc_info=True)

    def clear(self) -> None:
        """Drop all subscriptions (used by tests)."""
        self._subscribers.clear()
