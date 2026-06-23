"""Liveness analysis used by the `del` ("free intermediates") code generation.

The whole safety property of `del` rests on this: a variable must be released
only after its *last* consumer, never before. These tests pin that down on the
shapes that make naive analysis wrong — fan-out and late joins.
"""

from app.engine.codegen_common import last_consumer_index


def test_linear_chain() -> None:
    order = ["a", "b", "c"]
    edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
    # a dies once b (idx 1) runs; b once c (idx 2) runs; c has no consumer.
    assert last_consumer_index(order, edges) == {"a": 1, "b": 2}


def test_fanout_waits_for_last_consumer() -> None:
    # a feeds b (idx 1) and d (idx 3); it must survive until the later one.
    order = ["a", "b", "c", "d"]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "d"},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "d"},
    ]
    assert last_consumer_index(order, edges)["a"] == 3


def test_diamond() -> None:
    # a -> b, a -> c, b -> d, c -> d : a dies after max(pos b, pos c).
    order = ["a", "b", "c", "d"]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "c"},
        {"source": "b", "target": "d"},
        {"source": "c", "target": "d"},
    ]
    last = last_consumer_index(order, edges)
    assert last["a"] == 2  # c is the later consumer
    assert last["b"] == 3
    assert last["c"] == 3
    assert "d" not in last  # sink


def test_multi_input_join_keeps_each_input_until_its_join() -> None:
    # Two inputs feed a join much later in the order.
    order = ["in1", "in2", "mid", "join", "out"]
    edges = [
        {"source": "in1", "target": "mid"},
        {"source": "mid", "target": "join"},
        {"source": "in2", "target": "join"},
        {"source": "join", "target": "out"},
    ]
    last = last_consumer_index(order, edges)
    assert last["in2"] == 3  # not freed before the join at idx 3
    assert last["in1"] == 2
    assert last["mid"] == 3
    assert last["join"] == 4
