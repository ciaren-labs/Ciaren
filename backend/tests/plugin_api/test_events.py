"""Unit tests for the plugin EventBus — subscribe/emit, isolation, edge cases."""

from __future__ import annotations

import pytest

from app.plugin_api.events import EventBus, Hook


def test_emit_with_no_subscribers_is_noop():
    bus = EventBus()
    # Must not raise and must not create lingering state.
    bus.emit(Hook.before_node_execute, node_id="x")
    assert bus.subscriber_count(Hook.before_node_execute) == 0


def test_subscribe_and_emit_delivers_payload():
    bus = EventBus()
    seen: list[dict] = []
    bus.subscribe(Hook.after_node_execute, lambda **kw: seen.append(kw))
    bus.emit(Hook.after_node_execute, node_id="n1", status="success")
    assert seen == [{"node_id": "n1", "status": "success"}]


def test_string_and_enum_hook_are_equivalent():
    bus = EventBus()
    calls: list[str] = []
    # Subscribe with a raw string, emit with the enum (and vice versa).
    bus.subscribe("before_graph_execute", lambda **_: calls.append("a"))
    bus.subscribe(Hook.before_graph_execute, lambda **_: calls.append("b"))
    bus.emit("before_graph_execute")
    bus.emit(Hook.before_graph_execute)
    assert calls == ["a", "b", "a", "b"]


def test_duplicate_subscription_is_ignored():
    bus = EventBus()
    cb = lambda **_: None  # noqa: E731
    bus.subscribe(Hook.graph_validated, cb)
    bus.subscribe(Hook.graph_validated, cb)
    assert bus.subscriber_count(Hook.graph_validated) == 1


def test_subscribers_run_in_registration_order():
    bus = EventBus()
    order: list[int] = []
    for i in range(5):
        bus.subscribe(Hook.export_requested, (lambda i: lambda **_: order.append(i))(i))
    bus.emit(Hook.export_requested)
    assert order == [0, 1, 2, 3, 4]


def test_failing_subscriber_is_isolated():
    bus = EventBus()
    seen: list[str] = []

    def boom(**_):
        raise RuntimeError("plugin bug")

    bus.subscribe(Hook.after_graph_execute, boom)
    bus.subscribe(Hook.after_graph_execute, lambda **_: seen.append("ok"))
    # The bad subscriber must not stop the good one or propagate.
    bus.emit(Hook.after_graph_execute, run_id="r1")
    assert seen == ["ok"]


def test_unsubscribe_removes_callback():
    bus = EventBus()
    seen: list[int] = []
    cb = lambda **_: seen.append(1)  # noqa: E731
    bus.subscribe(Hook.plugin_enabled, cb)
    bus.unsubscribe(Hook.plugin_enabled, cb)
    bus.emit(Hook.plugin_enabled, plugin_id="p")
    assert seen == []


def test_unsubscribe_unknown_is_safe():
    bus = EventBus()
    bus.unsubscribe(Hook.plugin_disabled, lambda **_: None)  # never subscribed


def test_subscriber_may_unsubscribe_during_dispatch():
    bus = EventBus()
    seen: list[str] = []

    def once(**_):
        seen.append("once")
        bus.unsubscribe(Hook.graph_loaded, once)

    bus.subscribe(Hook.graph_loaded, once)
    bus.subscribe(Hook.graph_loaded, lambda **_: seen.append("other"))
    bus.emit(Hook.graph_loaded)
    bus.emit(Hook.graph_loaded)
    # `once` fired only the first time; `other` fired both times.
    assert seen == ["once", "other", "other"]


def test_clear_drops_all_subscriptions():
    bus = EventBus()
    bus.subscribe(Hook.before_node_execute, lambda **_: None)
    bus.clear()
    assert bus.subscriber_count(Hook.before_node_execute) == 0


@pytest.mark.parametrize("hook", list(Hook))
def test_every_hook_value_is_unique_and_stringy(hook: Hook):
    # Each hook's value is a plain str (JSON/log friendly) and distinct.
    assert isinstance(hook.value, str)
    assert sum(h.value == hook.value for h in Hook) == 1
