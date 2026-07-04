"""ML nodes are contributed by an independent provider.

This proves the Phase 5 goal: the open-core ETL core (BuiltinNodeProvider) is
complete on its own, and ML plugs in like any other provider — registerable and
unregisterable without touching the ETL core.
"""

from __future__ import annotations

import pytest

from app.engine.registry import is_ml_node, list_transformation_types, ml_node_types
from app.plugin_api import ServiceRegistry
from app.plugins.builtin import BuiltinNodeProvider, MlNodeProvider

_ML_AVAILABLE = bool(ml_node_types())


def test_core_provider_contributes_no_ml_nodes():
    reg = ServiceRegistry()
    reg.register_node_provider(BuiltinNodeProvider())
    ml_specs = [s for s in reg.node_specs() if s.requires_ml]
    assert ml_specs == []
    # …but it does contribute the ETL core (a known non-ML transform).
    assert reg.node_spec("filterRows") is not None
    assert reg.node_implementation("filterRows") is not None


def test_core_provider_has_no_ml_implementations():
    reg = ServiceRegistry()
    reg.register_node_provider(BuiltinNodeProvider())
    for node_type in list_transformation_types():
        if is_ml_node(node_type):
            assert reg.node_implementation(node_type) is None


@pytest.mark.skipif(not _ML_AVAILABLE, reason="core ML dependencies unavailable")
def test_ml_provider_contributes_only_ml_nodes():
    reg = ServiceRegistry()
    reg.register_node_provider(MlNodeProvider())
    specs = reg.node_specs()
    assert specs, "expected ML nodes when core ML dependencies are available"
    assert all(s.requires_ml for s in specs)
    assert all(s.provider == "ciaren.ml" for s in specs)
    # Implementations are present so ML nodes execute once registered.
    assert reg.node_implementation("mlTrainClassifier") is not None


@pytest.mark.skipif(not _ML_AVAILABLE, reason="core ML dependencies unavailable")
def test_core_and_ml_providers_are_disjoint_and_complete():
    core = ServiceRegistry()
    core.register_node_provider(BuiltinNodeProvider())
    ml = ServiceRegistry()
    ml.register_node_provider(MlNodeProvider())

    core_ids = {s.id for s in core.node_specs()}
    ml_ids = {s.id for s in ml.node_specs()}
    assert core_ids.isdisjoint(ml_ids)
    # Together they cover every registered transform (plus I/O on the core side).
    assert ml_ids == set(ml_node_types())


@pytest.mark.skipif(not _ML_AVAILABLE, reason="core ML dependencies unavailable")
def test_ml_provider_can_be_added_and_omitted_independently():
    # Omitting the ML provider yields a registry with no ML nodes…
    core_only = ServiceRegistry()
    core_only.register_node_provider(BuiltinNodeProvider())
    assert core_only.node_spec("mlTrainClassifier") is None
    # …adding it brings them in, without re-registering the core.
    core_only.register_node_provider(MlNodeProvider())
    assert core_only.node_spec("mlTrainClassifier") is not None
