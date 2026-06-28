"""The event bus is wired into the executor and registry lifecycle."""

from __future__ import annotations

import pandas as pd

from app.engine.executor import FlowExecutor, dataset_ref_key
from app.plugin_api import EventBus, Hook, PluginMetadata, ServiceRegistry
from app.plugin_api.providers import Plugin


def _identity_graph() -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }


def test_executor_emits_node_hooks(tmp_path):
    bus = EventBus()
    events: list[tuple[str, str]] = []
    bus.subscribe(Hook.before_node_execute, lambda **kw: events.append(("before", kw["node_id"])))
    bus.subscribe(Hook.after_node_execute, lambda **kw: events.append(("after", kw["node_id"])))

    in_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    FlowExecutor(events=bus).run_with_results(
        _identity_graph(),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name="pandas",
    )
    # Both nodes fire before+after, in topological order.
    assert events == [("before", "in1"), ("after", "in1"), ("before", "out1"), ("after", "out1")]


def test_executor_without_bus_does_not_emit(tmp_path):
    # The default (process-mode / no-plugin) path must not require a bus.
    in_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1]}).to_csv(in_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = FlowExecutor().run_with_results(
        _identity_graph(),
        dataset_paths={dataset_ref_key("ds1", None): in_csv},
        output_dir=out_dir,
        engine_name="pandas",
    )
    assert result.error is None


def test_after_node_hook_reports_failure(tmp_path):
    bus = EventBus()
    statuses: list[str] = []
    bus.subscribe(Hook.after_node_execute, lambda **kw: statuses.append(kw["status"]))

    # csvInput pointing at a missing dataset path -> the input node fails.
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    FlowExecutor(events=bus).run_with_results(
        _identity_graph(),
        dataset_paths={dataset_ref_key("ds1", None): tmp_path / "missing.csv"},
        output_dir=out_dir,
        engine_name="pandas",
    )
    assert statuses[0] == "failed"


class _SubscribingPlugin(Plugin):
    """Subscribes to a hook, then fails registration to test rollback."""

    def __init__(self, fail: bool) -> None:
        self.fail = fail

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(id="test.sub", name="Sub")

    def register(self, registry: ServiceRegistry) -> None:
        registry.events.subscribe(Hook.graph_validated, lambda **_: None)
        if self.fail:
            raise RuntimeError("boom after subscribing")


def test_failed_registration_rolls_back_subscriptions():
    registry = ServiceRegistry()
    try:
        registry.register_plugin(_SubscribingPlugin(fail=True))
    except RuntimeError:
        pass
    # The subscription made before the failure must have been rolled back.
    assert registry.events.subscriber_count(Hook.graph_validated) == 0


def test_successful_registration_keeps_subscriptions():
    registry = ServiceRegistry()
    registry.register_plugin(_SubscribingPlugin(fail=False))
    assert registry.events.subscriber_count(Hook.graph_validated) == 1
