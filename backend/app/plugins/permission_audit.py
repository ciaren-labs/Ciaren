# SPDX-License-Identifier: AGPL-3.0-only
"""Opt-in runtime enforcement of a plugin's *granted* permissions.

The permission model is otherwise advisory: enabling a plugin runs its Python with
the user's full privileges, and a manifest permission is only enforced where the
*host* mediates the action (e.g. a pickle model-load through ``ModelStore``). This
module adds a second, opt-in layer using a CPython audit hook (PEP 578): while a
plugin node executes, network / filesystem-write / subprocess / shell actions the
plugin did **not** declare+get granted are logged (``warn``) or blocked (``enforce``).

It is deliberately **not a sandbox**. A determined plugin can still escape via a
thread it spawns (a new thread starts with an empty context, so the scope below
does not follow it), a child process, or native code. Filesystem *reads* are never
blocked — the import system and pandas open files constantly, so denying reads
would break legitimate plugins. Treat this as "raise the bar + get an audit trail",
and keep genuinely sensitive logic server-side (see the marketplace plan §7).

Cost: an audit hook fires for the mapped events *process-wide* once installed, so
the hook is installed lazily only when a plugin actually executes under ``warn`` or
``enforce`` — ``off`` (the default) installs nothing and costs nothing. Once
installed a hook cannot be removed (PEP 578), but it is a cheap no-op whenever no
plugin scope is active.
"""

from __future__ import annotations

import contextvars
import logging
import os
import sys
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from app.plugin_api import Permission

logger = logging.getLogger("app.plugins.permission_audit")

_MODES = ("off", "warn", "enforce")

#: Audit event name -> the permission a plugin must have been granted to trigger it.
#: ``open`` is handled separately (its write-vs-read intent is in the arguments).
_EVENT_PERMISSION: dict[str, Permission] = {
    # network egress / listening
    "socket.connect": Permission.network,
    "socket.getaddrinfo": Permission.network,
    "socket.bind": Permission.network,
    # process spawning
    "subprocess.Popen": Permission.subprocess,
    "os.exec": Permission.subprocess,
    "os.spawn": Permission.subprocess,
    "os.posix_spawn": Permission.subprocess,
    "os.fork": Permission.subprocess,
    "os.forkpty": Permission.subprocess,
    # a shell command line specifically
    "os.system": Permission.shell,
    # filesystem mutations (reads are intentionally absent — see module docstring)
    "os.mkdir": Permission.filesystem_write,
    "os.rename": Permission.filesystem_write,
    "os.remove": Permission.filesystem_write,
    "os.rmdir": Permission.filesystem_write,
    "os.link": Permission.filesystem_write,
    "os.symlink": Permission.filesystem_write,
    "os.chmod": Permission.filesystem_write,
    "os.chown": Permission.filesystem_write,
    "os.truncate": Permission.filesystem_write,
}


@dataclass(frozen=True)
class _Scope:
    plugin_id: str
    granted: frozenset[Permission]
    enforce: bool  # True -> raise (enforce); False -> log only (warn)


#: The plugin currently executing on this thread/context, or ``None`` outside any
#: plugin call. Set only under ``warn``/``enforce`` so ``off`` is a true no-op.
_active: contextvars.ContextVar[_Scope | None] = contextvars.ContextVar("plugin_permission_scope", default=None)
#: Re-entrancy guard: our own work (logging, classification) must not recurse back
#: through the hook if it happens to trip an audited event.
_reentrant = threading.local()
_installed = False
_install_lock = threading.Lock()


def _writes_to_disk(mode: Any, flags: Any) -> bool:
    """Whether an ``open`` audit event represents a write. Builtin ``open`` passes a
    string ``mode`` (``"w"``/``"a"``/``"x"``/``"+"`` ⇒ write); ``os.open`` passes the
    O_* ``flags`` instead, so fall back to those."""
    if isinstance(mode, str):
        return any(c in mode for c in ("w", "a", "x", "+"))
    try:
        f = int(flags)
    except (TypeError, ValueError):
        return False
    return bool(f & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))


def _required_permission(event: str, args: Sequence[Any]) -> Permission | None:
    """The permission ``event`` requires, or ``None`` if it isn't gated."""
    perm = _EVENT_PERMISSION.get(event)
    if perm is not None:
        return perm
    if event == "open":
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        return Permission.filesystem_write if _writes_to_disk(mode, flags) else None
    return None


def _audit_hook(event: str, args: tuple[Any, ...]) -> None:
    scope = _active.get()
    if scope is None or getattr(_reentrant, "active", False):
        return
    _reentrant.active = True
    try:
        perm = _required_permission(event, args)
        if perm is None or perm in scope.granted:
            return
        detail = f"plugin {scope.plugin_id!r} attempted a {perm.value!r} action ({event}) it was not granted"
        if scope.enforce:
            raise PermissionError(detail)
        logger.warning("%s [permission audit: warn — not blocked]", detail)
    except PermissionError:
        raise  # the intended enforcement signal — propagate to abort the action
    except Exception:  # noqa: BLE001 — a hook bug must never break the operation
        logger.debug("permission audit hook error on %r", event, exc_info=True)
    finally:
        _reentrant.active = False


def _ensure_installed() -> None:
    global _installed
    if _installed:
        return
    with _install_lock:
        if not _installed:
            sys.addaudithook(_audit_hook)
            _installed = True


def normalize_mode(value: str | None) -> str:
    """A valid mode string (``off``/``warn``/``enforce``); unknown values read as
    ``off`` so a typo fails safe (advisory) rather than silently enforcing."""
    mode = (value or "off").strip().lower()
    return mode if mode in _MODES else "off"


def enforcement_mode() -> str:
    """The configured enforcement mode from settings."""
    from app.core.config import get_settings

    return normalize_mode(get_settings().PLUGIN_PERMISSION_ENFORCEMENT)


@contextmanager
def plugin_execution(plugin_id: str, granted: frozenset[Permission], mode: str) -> Iterator[None]:
    """Mark plugin code as executing so the audit hook enforces ``granted`` against
    it. A no-op under ``off`` (nothing is installed, no scope is set)."""
    if mode not in ("warn", "enforce"):
        yield
        return
    _ensure_installed()
    token = _active.set(_Scope(plugin_id=plugin_id, granted=frozenset(granted), enforce=(mode == "enforce")))
    try:
        yield
    finally:
        _active.reset(token)
