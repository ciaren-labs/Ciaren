"""The canonical typed graph view (``FlowNode`` / ``FlowEdge`` / ``FlowGraph``).

``FlowGraph`` keeps its ``nodes``/``edges`` as raw dicts so persistence and export
stay byte-faithful, while offering a typed lens for domain code. These tests pin
three properties that make the lens trustworthy: lossless round-trips (including
over every real demo graph), idempotent re-parsing, and structural validation
that behaves exactly as the old free function did — plus the permissive parsing
of malformed graphs the structural validator is meant to *report* on, not reject.
"""

from __future__ import annotations

import pytest

from app.demo.loader import build_demo_flows
from app.flow_schema import FlowGraph, FlowNode
from app.flow_schema.validate import graph_structure_issues

_DEMO_DATASETS = {
    name: name
    for name in (
        "customers.csv,orders.csv,products.csv,order_items.csv,leads.csv,web_events.csv,"
        "survey_responses.csv,regional_targets.csv,regional_actuals.csv,iris.csv,house_prices.csv"
    ).split(",")
}


# ---------------------------------------------------------------------------
# Round-trip fidelity
# ---------------------------------------------------------------------------


def test_roundtrip_preserves_extra_and_cosmetic_keys() -> None:
    raw = {
        "nodes": [
            {
                "id": "a",
                "type": "fillNulls",
                "position": {"x": 1, "y": 2},
                "data": {"label": "Fill Nulls", "config": {"columns": ["age"]}},
                "width": 220,  # cosmetic React Flow key
                "selected": True,
            }
        ],
        "edges": [{"id": "e1", "source": "a", "target": "b", "sourceHandle": "train"}],
        "engine": "polars",  # flow-level extra
        "parameters": [{"name": "cutoff", "type": "number"}],
    }
    graph = FlowGraph.model_validate(raw)
    assert graph.model_dump(mode="json", exclude_unset=True) == raw


@pytest.mark.parametrize("include_ml", [False, True])
def test_roundtrip_over_every_demo_graph(include_ml: bool) -> None:
    for _name, _desc, raw_graph in build_demo_flows(_DEMO_DATASETS, include_ml=include_ml):
        graph = FlowGraph.model_validate(raw_graph)
        assert graph.model_dump(mode="json", exclude_unset=True) == raw_graph


def test_reparse_is_idempotent() -> None:
    raw = {
        "nodes": [{"id": "a", "type": "join", "data": {"config": {"how": "inner"}}}],
        "edges": [{"source": "a", "target": "a"}],
    }
    once = FlowGraph.model_validate(raw).model_dump(mode="json", exclude_unset=True)
    twice = FlowGraph.model_validate(once).model_dump(mode="json", exclude_unset=True)
    assert once == twice


# ---------------------------------------------------------------------------
# Typed accessors
# ---------------------------------------------------------------------------


def test_typed_node_exposes_config_and_label() -> None:
    node = FlowNode.model_validate(
        {"id": "n", "type": "fillNulls", "data": {"label": "Fill", "config": {"strategy": "median"}}}
    )
    assert node.config == {"strategy": "median"}
    assert node.label == "Fill"


def test_typed_node_tolerates_missing_or_malformed_data() -> None:
    assert FlowNode.model_validate({"id": "n", "type": "t"}).config == {}
    assert FlowNode.model_validate({"id": "n", "type": "t"}).label is None
    # A non-dict config must not blow up the accessor.
    assert FlowNode.model_validate({"id": "n", "type": "t", "data": {"config": "oops"}}).config == {}


def test_typed_lens_never_rejects_malformed_but_plausible_graphs() -> None:
    """The parse-never-rejects contract: shapes the structural validator is meant
    to *report* on (not the parser) must coerce to safe defaults, not raise. This
    matters because a later slice will run typed_nodes()/typed_edges() over
    untrusted imported .flow JSON, where a single ``data: null`` node must not
    crash the whole parse."""
    graph = FlowGraph.model_validate(
        {
            "nodes": [
                {"id": "a", "type": "t", "data": None, "position": None},  # nulls
                {"id": 0, "type": ["weird"], "data": []},  # numeric id, non-str type, list data
            ],
            "edges": [
                {"source": 0, "target": ["x"], "sourceHandle": 7},  # non-string endpoints/handles
            ],
        }
    )
    nodes = graph.typed_nodes()
    assert nodes[0].data == {} and nodes[0].position == {} and nodes[0].config == {}
    assert nodes[1].id is None and nodes[1].type is None and nodes[1].data == {}
    (edge,) = graph.typed_edges()
    assert edge.source is None and edge.target is None and edge.source_handle is None


def test_typed_edge_reads_camelcase_handles() -> None:
    (edge,) = FlowGraph.model_validate(
        {"nodes": [], "edges": [{"source": "a", "target": "b", "sourceHandle": "train", "targetHandle": "in"}]}
    ).typed_edges()
    assert edge.source_handle == "train"
    assert edge.target_handle == "in"


def test_node_ids_and_types_skip_malformed() -> None:
    graph = FlowGraph.model_validate(
        {
            "nodes": [
                {"id": "a", "type": "fillNulls"},
                {"id": "b", "type": "join"},
                {"type": "orphan"},  # no id
                {"id": "c"},  # no type
                {"id": "d", "type": "fillNulls"},  # duplicate type
            ],
            "edges": [],
        }
    )
    assert graph.node_ids() == {"a", "b", "c", "d"}  # the idless node is skipped
    # Order-stable and de-duplicated across all typed nodes (parity with the old
    # missing_node_types, which counted a type regardless of whether the node had an id).
    assert graph.node_types() == ["fillNulls", "join", "orphan"]


# ---------------------------------------------------------------------------
# Structural validation parity
# ---------------------------------------------------------------------------


def test_sound_graph_has_no_structural_issues() -> None:
    graph = FlowGraph.model_validate(
        {
            "nodes": [{"id": "a", "type": "fileInput"}, {"id": "b", "type": "fileOutput"}],
            "edges": [{"source": "a", "target": "b"}],
        }
    )
    assert graph.structural_issues() == []
    assert graph_structure_issues(graph) == []  # free function delegates identically


def test_structural_issues_report_all_problems() -> None:
    graph = FlowGraph.model_validate(
        {
            "nodes": [
                {"type": "noid"},  # missing id
                {"id": "a", "type": "fillNulls"},
                {"id": "a", "type": "fillNulls"},  # duplicate id
                {"id": "b"},  # missing type
            ],
            "edges": [
                {"source": "a"},  # missing target
                {"source": "ghost", "target": "a"},  # unknown source
                {"source": "a", "target": "b"},  # fine
            ],
        }
    )
    issues = graph.structural_issues()
    assert "node[0] is missing an 'id'" in issues
    assert "duplicate node id 'a'" in issues
    assert "node 'b' is missing a 'type'" in issues
    assert "edge[0] is missing 'target'" in issues
    assert "edge[1] source 'ghost' references an unknown node" in issues
    # The delegating free function returns the exact same list.
    assert graph_structure_issues(graph) == issues


def test_empty_graph_is_structurally_sound() -> None:
    assert FlowGraph.model_validate({"nodes": [], "edges": []}).structural_issues() == []
