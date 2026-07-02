"""Shared code-generation driver helpers.

The core safety property is liveness: a variable must be released (or reused)
only after its *last* consumer, never before. These tests pin that down on the
shapes that make naive analysis wrong — fan-out and late joins — plus the
smaller shared helpers both drivers depend on (edge → variable resolution,
input-var collection, import ordering, del scheduling).
"""

from app.engine.codegen_common import (
    DelScheduler,
    collect_input_vars,
    edge_source_var,
    last_consumer_index,
    ordered_imports,
)


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


# --- edge -> variable resolution ---------------------------------------------

_OUTS = {"single": {"out": "df_1"}, "split": {"train": "df_2", "test": "df_3"}}


def test_edge_source_var_default_out_handle() -> None:
    assert edge_source_var(_OUTS, {"source": "single", "target": "x"}) == "df_1"


def test_edge_source_var_routes_source_handle() -> None:
    edge = {"source": "split", "target": "x", "sourceHandle": "test"}
    assert edge_source_var(_OUTS, edge) == "df_3"


def test_edge_source_var_unknown_handle_falls_back_to_first() -> None:
    edge = {"source": "split", "target": "x", "sourceHandle": "nope"}
    assert edge_source_var(_OUTS, edge) == "df_2"  # no 'out' either: first declared


def test_collect_input_vars_disambiguates_repeated_handles() -> None:
    # Variadic concat: three edges, all on the implicit "in" handle.
    edges = [
        {"source": "single", "target": "cat"},
        {"source": "split", "target": "cat", "sourceHandle": "train"},
        {"source": "split", "target": "cat", "sourceHandle": "test"},
    ]
    assert collect_input_vars(edges, _OUTS) == {"in": "df_1", "in_1": "df_2", "in_2": "df_3"}


def test_collect_input_vars_named_handles() -> None:
    edges = [
        {"source": "single", "target": "j", "targetHandle": "left"},
        {"source": "split", "target": "j", "targetHandle": "right", "sourceHandle": "train"},
    ]
    assert collect_input_vars(edges, _OUTS) == {"left": "df_1", "right": "df_2"}


# --- import ordering ----------------------------------------------------------


def test_ordered_imports_plain_before_from_each_sorted() -> None:
    imports = ["from sklearn.svm import SVC", "import numpy as np", "import joblib", "from a import b"]
    assert ordered_imports(imports) == [
        "import joblib",
        "import numpy as np",
        "from a import b",
        "from sklearn.svm import SVC",
    ]


# --- del scheduling -----------------------------------------------------------


def _scheduler(enabled: bool = True) -> DelScheduler:
    order = ["a", "b", "c", "d"]
    last_use = {"a": 2, "b": 3}  # a dies at idx 2, b at the final node
    return DelScheduler(order, last_use, enabled)


def test_del_scheduler_flushes_at_last_consumer() -> None:
    dels = _scheduler()
    dels.schedule("a", {"out": "df_1"})
    assert dels.flush(0) == []
    assert dels.flush(1) == []
    assert dels.flush(2) == ["del df_1"]
    assert dels.flush(2) == []  # popped, not repeated


def test_del_scheduler_never_frees_at_final_node() -> None:
    dels = _scheduler()
    dels.schedule("b", {"out": "df_2"})  # last consumer is idx 3 == final
    assert dels.flush(3) == []


def test_del_scheduler_skips_multi_output_nodes() -> None:
    dels = _scheduler()
    dels.schedule("a", {"train": "df_1", "test": "df_2"})
    assert dels.flush(2) == []


def test_del_scheduler_cancel_on_variable_reuse() -> None:
    dels = _scheduler()
    dels.schedule("a", {"out": "df_1"})
    dels.cancel(2, "df_1")  # the consumer at idx 2 took df_1 over
    assert dels.flush(2) == []


def test_del_scheduler_disabled_is_inert() -> None:
    dels = _scheduler(enabled=False)
    dels.schedule("a", {"out": "df_1"})
    assert dels.flush(2) == []
