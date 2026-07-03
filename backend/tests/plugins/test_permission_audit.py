"""Opt-in runtime enforcement of a plugin's granted permissions (audit hook)."""

from __future__ import annotations

import logging
import sys

import pandas as pd
import pytest

from app.core.config import get_settings
from app.engine.backends.base import get_engine
from app.plugin_api import NodeContext, NodeRuntime, NodeSpec, Permission, PortSpec
from app.plugins.adapter import PluginTransformation
from app.plugins.permission_audit import (
    enforcement_mode,
    normalize_mode,
    plugin_execution,
)

_NET_ARGS = (None, ("1.2.3.4", 80))  # synthetic socket.connect args (no real I/O)


def test_normalize_mode():
    assert normalize_mode("WARN") == "warn"
    assert normalize_mode(" Enforce ") == "enforce"
    assert normalize_mode(None) == "off"
    assert normalize_mode("nonsense") == "off"  # unknown fails safe to advisory


def test_off_mode_is_a_noop():
    with plugin_execution("p", frozenset(), "off"):
        sys.audit("socket.connect", *_NET_ARGS)  # must not raise


def test_no_enforcement_outside_a_plugin_scope():
    # Core/host code is never gated — only code inside plugin_execution is.
    sys.audit("socket.connect", *_NET_ARGS)  # must not raise


def test_enforce_blocks_ungranted_network():
    with plugin_execution("acme.tool", frozenset(), "enforce"):
        with pytest.raises(PermissionError, match="network"):
            sys.audit("socket.connect", *_NET_ARGS)


def test_enforce_allows_granted_network():
    with plugin_execution("acme.tool", frozenset({Permission.network}), "enforce"):
        sys.audit("socket.connect", *_NET_ARGS)  # granted → no raise


def test_enforce_blocks_ungranted_subprocess():
    with plugin_execution("acme.tool", frozenset(), "enforce"):
        with pytest.raises(PermissionError, match="subprocess"):
            sys.audit("subprocess.Popen", "/bin/ls", ["ls"], None, None)


def test_enforce_blocks_ungranted_file_write_and_nothing_is_written(tmp_path):
    target = tmp_path / "written.txt"
    with plugin_execution("acme.tool", frozenset(), "enforce"):
        with pytest.raises(PermissionError, match="filesystem_write"):
            open(target, "w")  # noqa: SIM115 — the open is what we expect to be blocked
    assert not target.exists()  # blocked before the file was created


def test_enforce_allows_file_write_when_granted(tmp_path):
    target = tmp_path / "ok.txt"
    with plugin_execution("acme.tool", frozenset({Permission.filesystem_write}), "enforce"):
        with open(target, "w") as fh:
            fh.write("hi")
    assert target.read_text() == "hi"


def test_reads_are_never_blocked(tmp_path):
    existing = tmp_path / "data.txt"
    existing.write_text("payload")  # created outside any plugin scope
    with plugin_execution("acme.tool", frozenset(), "enforce"):
        # No filesystem_read grant, yet a read must succeed — the import system and
        # pandas open files constantly, so denying reads would break plugins.
        with open(existing) as fh:
            assert fh.read() == "payload"


def test_warn_mode_logs_but_does_not_block(caplog):
    with caplog.at_level(logging.WARNING, logger="app.plugins.permission_audit"):
        with plugin_execution("acme.tool", frozenset(), "warn"):
            sys.audit("socket.connect", *_NET_ARGS)  # no raise in warn mode
    assert any("network" in r.getMessage() and "acme.tool" in r.getMessage() for r in caplog.records)


def test_enforcement_mode_reads_settings(monkeypatch):
    monkeypatch.setenv("CIAREN_PLUGIN_PERMISSION_ENFORCEMENT", "enforce")
    get_settings.cache_clear()
    try:
        assert enforcement_mode() == "enforce"
        monkeypatch.setenv("CIAREN_PLUGIN_PERMISSION_ENFORCEMENT", "typo")
        get_settings.cache_clear()
        assert enforcement_mode() == "off"
    finally:
        get_settings.cache_clear()


# -- wiring: enforcement is applied through the node-execution adapter ---------


class _ConnectingRuntime(NodeRuntime):
    """A node whose execution attempts a network action."""

    def execute_with_context(self, inputs, config, context):
        sys.audit("socket.connect", *_NET_ARGS)
        return {"out": inputs["in"]}


def _run(context: NodeContext):
    spec = NodeSpec(
        id="t.net",
        label="Net",
        category="columns",
        inputs=(PortSpec(id="in"),),
        outputs=(PortSpec(id="out"),),
    )
    engine = get_engine("pandas")
    frame = engine.from_pandas(pd.DataFrame({"a": [1]}))
    return PluginTransformation(spec, _ConnectingRuntime(), context).execute(engine, {"in": frame}, {})


def test_adapter_enforces_ungranted_permission(monkeypatch):
    monkeypatch.setenv("CIAREN_PLUGIN_PERMISSION_ENFORCEMENT", "enforce")
    get_settings.cache_clear()
    try:
        with pytest.raises(PermissionError, match="network"):
            _run(NodeContext(plugin_id="acme.net", permissions=frozenset()))
        # Granting the permission lets the same node run.
        out = _run(NodeContext(plugin_id="acme.net", permissions=frozenset({Permission.network})))
        assert "out" in out
    finally:
        get_settings.cache_clear()


def test_adapter_does_not_enforce_when_off(monkeypatch):
    monkeypatch.setenv("CIAREN_PLUGIN_PERMISSION_ENFORCEMENT", "off")
    get_settings.cache_clear()
    try:
        out = _run(NodeContext(plugin_id="acme.net", permissions=frozenset()))
        assert "out" in out  # advisory: ungranted network action is not blocked
    finally:
        get_settings.cache_clear()
