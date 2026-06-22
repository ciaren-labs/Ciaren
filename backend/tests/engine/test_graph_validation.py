"""Connection-topology validation in :func:`validate_graph`.

These tests try to break the wiring rules that the frontend enforces but the
API could otherwise accept, ensuring the backend (the source of truth) rejects
them with a clear error rather than silently dropping inputs or crashing.
"""

import pytest

from app.engine.graph import GraphValidationError, validate_graph


def _node(node_id, node_type, config=None):
    return {"id": node_id, "type": node_type, "data": {"config": config or {}}}


def _edge(source, target, target_handle=None):
    e = {"id": f"e_{source}_{target}", "source": source, "target": target}
    if target_handle is not None:
        e["targetHandle"] = target_handle
    return e


def _input(node_id="in1", dataset_id="ds1"):
    return _node(node_id, "csvInput", {"dataset_id": dataset_id})


# -- Happy paths ----------------------------------------------------------


def test_simple_pipeline_is_valid():
    graph = {
        "nodes": [_input(), _node("drop", "dropNulls"), _node("out", "csvOutput")],
        "edges": [_edge("in1", "drop"), _edge("drop", "out")],
    }
    validate_graph(graph)  # no raise


def test_join_with_both_sides_is_valid():
    graph = {
        "nodes": [
            _input("l"),
            _input("r"),
            _node("j", "join", {"on": "id"}),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("l", "j", "left"),
            _edge("r", "j", "right"),
            _edge("j", "out"),
        ],
    }
    validate_graph(graph)


def test_concat_with_two_inputs_is_valid():
    graph = {
        "nodes": [
            _input("a"),
            _input("b"),
            _node("c", "concatRows"),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("a", "c"), _edge("b", "c"), _edge("c", "out")],
    }
    validate_graph(graph)


def test_output_fan_out_from_one_node_is_valid():
    # One transform feeding two outputs (branching) is allowed.
    graph = {
        "nodes": [
            _input(),
            _node("drop", "dropNulls"),
            _node("o1", "csvOutput"),
            _node("o2", "parquetOutput"),
        ],
        "edges": [_edge("in1", "drop"), _edge("drop", "o1"), _edge("drop", "o2")],
    }
    validate_graph(graph)


# -- Break it -------------------------------------------------------------


def test_two_edges_into_single_input_rejected():
    graph = {
        "nodes": [
            _input("a"),
            _input("b"),
            _node("drop", "dropNulls"),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("a", "drop"),
            _edge("b", "drop"),  # second edge into the single 'in' handle
            _edge("drop", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="only one connection"):
        validate_graph(graph)


def test_join_missing_a_side_rejected():
    graph = {
        "nodes": [_input("l"), _node("j", "join", {"on": "id"}), _node("out", "csvOutput")],
        "edges": [_edge("l", "j", "left"), _edge("j", "out")],
    }
    with pytest.raises(GraphValidationError, match="right"):
        validate_graph(graph)


def test_output_with_no_input_rejected():
    graph = {
        "nodes": [_input(), _node("out", "csvOutput")],
        "edges": [],
    }
    with pytest.raises(GraphValidationError, match="exactly one input"):
        validate_graph(graph)


def test_output_with_two_inputs_rejected():
    graph = {
        "nodes": [
            _input("a"),
            _input("b"),
            _node("out", "csvOutput"),
        ],
        "edges": [_edge("a", "out"), _edge("b", "out")],
    }
    with pytest.raises(GraphValidationError, match="exactly one input"):
        validate_graph(graph)


def test_input_node_with_incoming_edge_rejected():
    graph = {
        "nodes": [_input("a"), _input("b"), _node("out", "csvOutput")],
        "edges": [_edge("a", "b"), _edge("b", "out")],
    }
    with pytest.raises(GraphValidationError, match="cannot have an incoming"):
        validate_graph(graph)


def test_input_node_without_dataset_rejected():
    graph = {
        "nodes": [_input("a", dataset_id=""), _node("out", "csvOutput")],
        "edges": [_edge("a", "out")],
    }
    with pytest.raises(GraphValidationError, match="no dataset"):
        validate_graph(graph)


def test_edge_to_unknown_handle_rejected():
    graph = {
        "nodes": [_input(), _node("drop", "dropNulls"), _node("out", "csvOutput")],
        "edges": [
            _edge("in1", "drop", "wat"),  # dropNulls only has 'in'
            _edge("drop", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="unknown input"):
        validate_graph(graph)


def test_transform_with_no_input_rejected():
    graph = {
        "nodes": [_input(), _node("drop", "dropNulls"), _node("out", "csvOutput")],
        "edges": [_edge("drop", "out")],  # drop has no upstream
    }
    with pytest.raises(GraphValidationError, match="not connected"):
        validate_graph(graph)
