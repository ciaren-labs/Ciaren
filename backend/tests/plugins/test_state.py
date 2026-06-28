"""Unit tests for the persisted plugin state store."""

from __future__ import annotations

import json
import warnings

from app.plugin_api import Permission
from app.plugins.state import PluginStateStore


def test_defaults_for_unknown_plugin(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    assert store.is_enabled("nope") is True  # enabled by default
    assert store.granted("nope") == set()
    assert store.entry("nope") is None


def test_disable_then_enable_persists(tmp_path):
    path = tmp_path / "s.json"
    store = PluginStateStore(path)
    store.set_enabled("p1", False)
    store.save()
    # A fresh store reads the persisted value.
    assert PluginStateStore(path).is_enabled("p1") is False

    store2 = PluginStateStore(path)
    store2.set_enabled("p1", True)
    store2.save()
    assert PluginStateStore(path).is_enabled("p1") is True


def test_grant_and_revoke(tmp_path):
    path = tmp_path / "s.json"
    store = PluginStateStore(path)
    store.grant("p1", [Permission.network, Permission.credentials])
    store.save()

    reread = PluginStateStore(path)
    assert reread.granted("p1") == {Permission.network, Permission.credentials}

    reread.revoke("p1", [Permission.network])
    reread.save()
    assert PluginStateStore(path).granted("p1") == {Permission.credentials}


def test_grant_is_idempotent(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    store.grant("p1", [Permission.network])
    store.grant("p1", [Permission.network])
    entry = store.entry("p1")
    assert entry is not None
    assert entry.granted_permissions == [Permission.network]


def test_grant_coerces_raw_permission_strings(tmp_path):
    """Callers may pass raw permission strings (CLI, internal helpers). They must
    be stored as ``Permission`` members so the model round-trips and serializes
    cleanly — no Pydantic 'expected enum' warning, no type drift."""
    path = tmp_path / "s.json"
    store = PluginStateStore(path)
    store.grant("p1", ["network", "credentials"])  # raw strings, not enum members

    entry = store.entry("p1")
    assert entry is not None
    assert all(isinstance(p, Permission) for p in entry.granted_permissions)

    # Saving must not emit a serialization warning.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        store.save()

    # …and the persisted JSON holds the plain permission values, re-read as enums.
    on_disk = json.loads(path.read_text())["plugins"]["p1"]["granted_permissions"]
    assert on_disk == ["network", "credentials"]
    assert PluginStateStore(path).granted("p1") == {Permission.network, Permission.credentials}


def test_revoke_accepts_raw_permission_strings(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    store.grant("p1", [Permission.network, Permission.credentials])
    store.revoke("p1", ["network"])  # raw string still matches the stored enum
    assert store.granted("p1") == {Permission.credentials}


def test_missing_permissions(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    store.grant("p1", [Permission.network])
    missing = store.missing_permissions("p1", [Permission.network, Permission.credentials])
    assert missing == [Permission.credentials]


def test_save_is_noop_when_not_dirty(tmp_path):
    path = tmp_path / "s.json"
    store = PluginStateStore(path)
    store.save()  # nothing changed
    assert not path.exists()  # never written


def test_note_seen_records_first_seen_once(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    store.note_seen("p1")
    first = store.entry("p1").first_seen
    assert first  # an ISO timestamp was recorded
    store.note_seen("p1")  # second call must not overwrite
    assert store.entry("p1").first_seen == first


def test_corrupt_state_file_starts_fresh(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{ not valid json", encoding="utf-8")
    store = PluginStateStore(path)  # must not raise
    assert store.is_enabled("anything") is True


def test_atomic_write_leaves_no_tmp(tmp_path):
    path = tmp_path / "s.json"
    store = PluginStateStore(path)
    store.set_enabled("p1", False)
    store.save()
    assert path.exists()
    assert json.loads(path.read_text())["plugins"]["p1"]["enabled"] is False
    assert not (tmp_path / "s.json.tmp").exists()


def test_forget_removes_entry(tmp_path):
    store = PluginStateStore(tmp_path / "s.json")
    store.set_enabled("p1", False)
    store.forget("p1")
    assert store.entry("p1") is None
    assert store.is_enabled("p1") is True  # back to default
