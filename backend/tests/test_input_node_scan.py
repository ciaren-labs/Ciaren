"""Unit coverage for the input-node graph scans that now use the canonical
``FlowGraph`` typed lens: ``dataset_resolver._input_refs`` (run/preview path,
resolves each file-input node's dataset reference) and
``flow_service._references_dataset`` (dataset lineage feeding the delete cascade).

These were raw-dict pokes. The lens preserves their behavior on every well-formed
graph (same refs / same bool / same "no dataset selected" error) and is strictly
*more* robust on malformed nodes: a ``data: null`` or non-dict ``config`` used to
raise ``AttributeError`` (HTTP 500) and now degrades gracefully — the tests below
that exercise malformed nodes assert the improved behavior, not preserved parity.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.engine.node_kinds import FILE_INPUT_TYPE
from app.engine.node_kinds import INPUT_SOURCE_TYPES as _LEGACY_FILE_INPUT_TYPES
from app.services.dataset_resolver import _input_refs
from app.services.flow_service import _references_dataset

_LEGACY_INPUT = next(iter(_LEGACY_FILE_INPUT_TYPES))


def _input_node(node_id: str, node_type: str, config: dict) -> dict:
    return {"id": node_id, "type": node_type, "data": {"label": "x", "config": config}}


# ---------------------------------------------------------------------------
# _input_refs
# ---------------------------------------------------------------------------


def test_input_refs_reads_id_and_pinned_version() -> None:
    graph = {
        "nodes": [_input_node("in", FILE_INPUT_TYPE, {"dataset_id": "ds1", "dataset_version": 3})],
        "edges": [],
    }
    assert _input_refs(graph) == {("ds1", 3)}


def test_input_refs_version_defaults_to_none() -> None:
    graph = {"nodes": [_input_node("in", FILE_INPUT_TYPE, {"dataset_id": "ds1"})], "edges": []}
    assert _input_refs(graph) == {("ds1", None)}


def test_input_refs_recognizes_legacy_input_types() -> None:
    graph = {"nodes": [_input_node("in", _LEGACY_INPUT, {"dataset_id": "ds9"})], "edges": []}
    assert _input_refs(graph) == {("ds9", None)}


def test_input_refs_ignores_non_input_nodes() -> None:
    graph = {
        "nodes": [
            _input_node("in", FILE_INPUT_TYPE, {"dataset_id": "ds1"}),
            _input_node("mid", "fillNulls", {"dataset_id": "not-a-real-binding"}),
        ],
        "edges": [],
    }
    assert _input_refs(graph) == {("ds1", None)}


def test_input_refs_dedupes_identical_references() -> None:
    graph = {
        "nodes": [
            _input_node("in1", FILE_INPUT_TYPE, {"dataset_id": "ds1", "dataset_version": 2}),
            _input_node("in2", FILE_INPUT_TYPE, {"dataset_id": "ds1", "dataset_version": 2}),
        ],
        "edges": [],
    }
    assert _input_refs(graph) == {("ds1", 2)}


def test_input_refs_raises_when_dataset_unselected() -> None:
    graph = {"nodes": [_input_node("in_lonely", FILE_INPUT_TYPE, {})], "edges": []}
    with pytest.raises(ValidationError, match="in_lonely.*no dataset selected"):
        _input_refs(graph)


def test_input_refs_tolerates_malformed_data_as_unselected() -> None:
    # Robustness improvement (the old raw-dict poke raised AttributeError -> 500):
    # a node whose data is null now degrades to the friendly "no dataset selected"
    # rather than crashing the scan.
    graph = {"nodes": [{"id": "in", "type": FILE_INPUT_TYPE, "data": None}], "edges": []}
    with pytest.raises(ValidationError, match="no dataset selected"):
        _input_refs(graph)


def test_input_refs_empty_graph() -> None:
    assert _input_refs({"nodes": [], "edges": []}) == set()


# ---------------------------------------------------------------------------
# _references_dataset
# ---------------------------------------------------------------------------


def test_references_dataset_true_when_input_binds_it() -> None:
    graph = {"nodes": [_input_node("in", FILE_INPUT_TYPE, {"dataset_id": "target"})], "edges": []}
    assert _references_dataset(graph, "target") is True


def test_references_dataset_false_when_absent() -> None:
    graph = {"nodes": [_input_node("in", FILE_INPUT_TYPE, {"dataset_id": "other"})], "edges": []}
    assert _references_dataset(graph, "target") is False


def test_references_dataset_ignores_non_input_nodes() -> None:
    # Only input nodes bind datasets; a transform coincidentally carrying the id
    # must not count as lineage.
    graph = {"nodes": [_input_node("mid", "fillNulls", {"dataset_id": "target"})], "edges": []}
    assert _references_dataset(graph, "target") is False


def test_references_dataset_empty_graph() -> None:
    assert _references_dataset({"nodes": [], "edges": []}, "target") is False


def test_references_dataset_tolerates_malformed_node() -> None:
    # Lineage feeds the delete/disable cascade, so a single malformed node must
    # not 500 the whole query (old raw-dict poke did): a non-dict config simply
    # yields no binding -> False.
    graph = {"nodes": [{"id": "in", "type": FILE_INPUT_TYPE, "data": {"config": "oops"}}], "edges": []}
    assert _references_dataset(graph, "target") is False
