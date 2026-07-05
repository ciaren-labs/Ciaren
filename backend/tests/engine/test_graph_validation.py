"""Connection-topology validation in :func:`validate_graph`.

These tests try to break the wiring rules that the frontend enforces but the
API could otherwise accept, ensuring the backend (the source of truth) rejects
them with a clear error rather than silently dropping inputs or crashing.
"""

import pytest

from app.engine.graph import GraphValidationError, validate_graph, validate_node_configs


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


def test_cycle_detection_works():
    """A back-edge that creates a cycle must be detected."""
    graph = {
        "nodes": [_input("in1"), _node("a", "dropNulls"), _node("b", "dropNulls"), _node("out", "csvOutput")],
        "edges": [
            _edge("in1", "a"),
            _edge("a", "b"),
            _edge("b", "a"),  # cycle: a -> b -> a
            _edge("b", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="[Cc]ycle"):
        validate_graph(graph)


def test_cycle_detection_is_iterative_for_large_graphs():
    """The cycle-detection DFS must not hit Python's recursion limit for deep graphs.

    Builds a linear chain of 2000 nodes (well past the default recursion limit of
    1000) and asserts both a valid chain and a cyclic one are handled correctly.
    """
    import sys

    n = sys.getrecursionlimit() + 500  # deliberately exceeds the recursion limit

    # Valid deep chain: in -> t_0 -> t_1 -> ... -> t_{n-1} -> out
    nodes = [_input("in1")]
    edges = []
    for i in range(n):
        nodes.append(_node(f"t{i}", "dropNulls"))
    nodes.append(_node("out", "csvOutput"))

    edges.append(_edge("in1", "t0"))
    for i in range(n - 1):
        edges.append(_edge(f"t{i}", f"t{i + 1}"))
    edges.append(_edge(f"t{n - 1}", "out"))

    validate_graph({"nodes": nodes, "edges": edges})  # must not raise or stack-overflow

    # Cyclic: add a back-edge from the last transform to the first
    edges.append(_edge(f"t{n - 1}", "t0"))
    with pytest.raises(GraphValidationError, match="[Cc]ycle"):
        validate_graph({"nodes": nodes, "edges": edges})


# -- model handles (model wires are type-checked) ---------------------------


def _ml_input(node_id="in1", dataset_id="ds1"):
    return _node(node_id, "csvInput", {"dataset_id": dataset_id})


def test_model_to_model_handle_is_valid():
    # mlTrain (single model output) -> mlPredict.model + featureImportance.model.
    graph = {
        "nodes": [
            _ml_input(),
            _node("tr", "mlTrainRegressor", {"model_type": "ridge", "target_column": "y", "seed": 1}),
            _node("pr", "mlPredict"),
            _node("fi", "featureImportance"),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in1", "tr"),
            _edge("in1", "pr"),  # data into mlPredict's "in"
            _edge("tr", "pr", "model"),
            _edge("tr", "fi", "model"),
            _edge("pr", "out"),
        ],
    }
    validate_graph(graph)


def test_model_into_data_input_rejected():
    # A trained model wired into a node's data "in" handle must be rejected.
    graph = {
        "nodes": [
            _ml_input(),
            _node("tr", "mlTrainRegressor", {"model_type": "ridge", "target_column": "y", "seed": 1}),
            _node("drop", "dropNulls"),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in1", "tr"),
            _edge("tr", "drop"),  # model -> data input
            _edge("drop", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="model can only connect to a model input"):
        validate_graph(graph)


def test_data_into_model_input_rejected():
    # A plain dataframe wired into a model input must be rejected.
    graph = {
        "nodes": [
            _ml_input(),
            _node("fi", "featureImportance"),
            _node("out", "csvOutput"),
        ],
        "edges": [
            _edge("in1", "fi", "model"),  # data -> model input
            _edge("fi", "out"),
        ],
    }
    with pytest.raises(GraphValidationError, match="needs a model reference"):
        validate_graph(graph)


# -- ancestor_subgraph --------------------------------------------------------


def _n(nid: str, ntype: str = "dropNulls") -> dict:
    return {"id": nid, "type": ntype, "data": {"config": {}}}


def _e(src: str, dst: str, **extra) -> dict:
    return {"id": f"{src}-{dst}", "source": src, "target": dst, **extra}


def test_ancestor_subgraph_keeps_only_upstream_slice():
    from app.engine.graph import ancestor_subgraph

    graph = {
        "engine": "polars",
        "parameters": [{"name": "keep", "type": "integer", "default": 1}],
        "nodes": [_n("in", "csvInput"), _n("a"), _n("b"), _n("sibling"), _n("down")],
        "edges": [_e("in", "a"), _e("a", "b"), _e("in", "sibling"), _e("b", "down")],
    }
    sub = ancestor_subgraph(graph, "b")
    assert {n["id"] for n in sub["nodes"]} == {"in", "a", "b"}
    assert {(e["source"], e["target"]) for e in sub["edges"]} == {("in", "a"), ("a", "b")}
    # Flow-level keys ride along untouched.
    assert sub["engine"] == "polars"
    assert sub["parameters"] == graph["parameters"]


def test_ancestor_subgraph_diamond_keeps_both_parents():
    from app.engine.graph import ancestor_subgraph

    graph = {
        "nodes": [_n("in", "csvInput"), _n("l"), _n("r"), _n("j", "join")],
        "edges": [
            _e("in", "l"),
            _e("in", "r"),
            _e("l", "j", targetHandle="left"),
            _e("r", "j", targetHandle="right"),
        ],
    }
    sub = ancestor_subgraph(graph, "j")
    assert {n["id"] for n in sub["nodes"]} == {"in", "l", "r", "j"}
    # Handle metadata on kept edges is preserved verbatim.
    handles = {e.get("targetHandle") for e in sub["edges"]}
    assert {"left", "right"} <= handles


def test_ancestor_subgraph_unknown_node_raises():
    import pytest as _pytest

    from app.engine.graph import GraphValidationError, ancestor_subgraph

    with _pytest.raises(GraphValidationError, match="ghost"):
        ancestor_subgraph({"nodes": [_n("a")], "edges": []}, "ghost")


def test_ancestor_subgraph_keeps_dangling_edges_into_the_slice():
    # Traversal skips the unknown source, but the corrupt edge itself stays in
    # the slice so downstream validate_graph rejects the graph instead of the
    # target node silently computing with one input missing.
    from app.engine.graph import ancestor_subgraph

    graph = {
        "nodes": [_n("a"), _n("b")],
        "edges": [_e("missing", "b"), _e("a", "b")],
    }
    sub = ancestor_subgraph(graph, "b")
    assert {n["id"] for n in sub["nodes"]} == {"a", "b"}
    assert {(e["source"], e["target"]) for e in sub["edges"]} == {("missing", "b"), ("a", "b")}


# -- Node-config validation (validate_node_configs) ------------------------


def _configured_graph(config):
    return {
        "nodes": [_input(), _node("sel", "selectColumns", config), _node("out", "csvOutput")],
        "edges": [_edge("in1", "sel"), _edge("sel", "out")],
    }


def test_valid_node_configs_pass():
    validate_node_configs(_configured_graph({"columns": ["name"]}))  # no raise


def test_missing_required_config_rejected_with_node_label():
    graph = _configured_graph({})
    graph["nodes"][1]["data"]["label"] = "Pick columns"
    with pytest.raises(GraphValidationError, match=r"Pick columns: .*columns"):
        validate_node_configs(graph)


def test_missing_required_config_falls_back_to_node_type_label():
    with pytest.raises(GraphValidationError, match="selectColumns"):
        validate_node_configs(_configured_graph({}))


def test_unknown_node_type_rejected():
    graph = {
        "nodes": [_input(), _node("x", "notATransform"), _node("out", "csvOutput")],
        "edges": [_edge("in1", "x"), _edge("x", "out")],
    }
    with pytest.raises(GraphValidationError, match="Unknown node type"):
        validate_node_configs(graph)


def test_input_and_output_nodes_are_skipped():
    # Input/output config rules live in validate_graph; validate_node_configs
    # must not require e.g. a dataset on an input node.
    graph = {
        "nodes": [_node("in1", "csvInput"), _node("out", "csvOutput")],
        "edges": [_edge("in1", "out")],
    }
    validate_node_configs(graph)  # no raise
