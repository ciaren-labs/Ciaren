"""Local, persisted plugin state: which plugins are enabled and which
permissions the user has granted them.

This is the *trust/UX boundary* the architecture plan describes: a drop-in plugin
that declares permissions stays **pending** (not loaded, so its code never runs)
until the user approves it, and any plugin can be disabled. State is a small JSON
file under the data dir so it survives restarts and is easy to inspect or wipe.

Python plugins are not sandboxed — this gates *loading*, not runtime syscalls —
so the boundary matters most before a plugin's entry point is ever imported.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.plugin_api import Permission

logger = logging.getLogger("app.plugins.state")

STATE_FILENAME = "plugin_state.json"
STATE_ENV_VAR = "FLOWFRAME_PLUGIN_STATE_FILE"


class PluginStateEntry(BaseModel):
    """Per-plugin persisted state."""

    # Re-validate on assignment so callers that mutate ``granted_permissions``
    # with raw permission strings (CLI, internal helpers) still store proper
    # ``Permission`` members — otherwise ``model_dump(mode="json")`` emits a
    # serialization warning and the in-memory value type drifts from the schema.
    model_config = ConfigDict(validate_assignment=True)

    enabled: bool = True
    granted_permissions: list[Permission] = Field(default_factory=list)
    #: ISO-8601 timestamp the plugin was first discovered (for "new plugin" UX).
    first_seen: str = ""
    #: How the package verified when it was installed: ``trusted`` | ``untrusted`` |
    #: ``unsigned`` | ``invalid`` | "" (unknown, e.g. a hand-dropped directory).
    signature: str = ""


def default_state_path() -> Path:
    """Where plugin state lives: ``FLOWFRAME_PLUGIN_STATE_FILE`` if set, else
    ``<DATA_DIR>/plugin_state.json``."""
    override = os.environ.get(STATE_ENV_VAR)
    if override:
        return Path(override).expanduser()
    from app.core.config import get_settings

    return Path(get_settings().DATA_DIR) / STATE_FILENAME


class PluginStateStore:
    """Reads/writes the plugin-state JSON file and answers gating queries.

    Mutations mark the store dirty; call :meth:`save` to persist (the loader does
    this once after discovery, and the API does it after each change).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_path()
        self._entries: dict[str, PluginStateEntry] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for plugin_id, data in (raw.get("plugins") or {}).items():
                self._entries[plugin_id] = PluginStateEntry.model_validate(data)
        except Exception:  # noqa: BLE001 — a corrupt state file must not break startup
            logger.warning("Could not read plugin state %s; starting fresh.", self.path, exc_info=True)
            self._entries = {}

    def save(self) -> None:
        if not self._dirty:
            return
        payload = {"plugins": {pid: e.model_dump(mode="json") for pid, e in self._entries.items()}}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically so a crash mid-write can't truncate the state file.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False

    # -- queries --------------------------------------------------------------

    def entry(self, plugin_id: str) -> PluginStateEntry | None:
        return self._entries.get(plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        """Plugins are enabled by default; only an explicit disable turns one off."""
        entry = self._entries.get(plugin_id)
        return True if entry is None else entry.enabled

    def granted(self, plugin_id: str) -> set[Permission]:
        entry = self._entries.get(plugin_id)
        return set(entry.granted_permissions) if entry else set()

    def signature(self, plugin_id: str) -> str:
        """The install-time signature trust outcome, or "" if unknown."""
        entry = self._entries.get(plugin_id)
        return entry.signature if entry else ""

    def missing_permissions(self, plugin_id: str, required: Iterable[Permission]) -> list[Permission]:
        granted = self.granted(plugin_id)
        return [p for p in required if p not in granted]

    # -- mutations ------------------------------------------------------------

    def note_seen(self, plugin_id: str) -> None:
        """Record first discovery of a plugin (no-op if already known)."""
        if plugin_id not in self._entries:
            self._entries[plugin_id] = PluginStateEntry(first_seen=datetime.now(UTC).isoformat())
            self._dirty = True

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        entry = self._entries.setdefault(plugin_id, PluginStateEntry(first_seen=datetime.now(UTC).isoformat()))
        if entry.enabled != enabled:
            entry.enabled = enabled
            self._dirty = True

    def set_signature(self, plugin_id: str, outcome: str) -> None:
        """Record how a package verified at install time, for later display."""
        entry = self._entries.setdefault(plugin_id, PluginStateEntry(first_seen=datetime.now(UTC).isoformat()))
        if entry.signature != outcome:
            entry.signature = outcome
            self._dirty = True

    def grant(self, plugin_id: str, permissions: Iterable[Permission | str]) -> None:
        entry = self._entries.setdefault(plugin_id, PluginStateEntry(first_seen=datetime.now(UTC).isoformat()))
        current = list(entry.granted_permissions)
        # Coerce raw strings (CLI / API) to Permission members so the model
        # round-trips and serializes without a Pydantic "expected enum" warning.
        for perm in (Permission(p) for p in permissions):
            if perm not in current:
                current.append(perm)
                self._dirty = True
        entry.granted_permissions = current

    def revoke(self, plugin_id: str, permissions: Iterable[Permission | str]) -> None:
        entry = self._entries.get(plugin_id)
        if entry is None:
            return
        to_remove = {Permission(p) for p in permissions}
        kept = [p for p in entry.granted_permissions if p not in to_remove]
        if len(kept) != len(entry.granted_permissions):
            entry.granted_permissions = kept
            self._dirty = True

    def forget(self, plugin_id: str) -> None:
        """Drop a plugin's state entirely (used when uninstalling)."""
        if plugin_id in self._entries:
            del self._entries[plugin_id]
            self._dirty = True
