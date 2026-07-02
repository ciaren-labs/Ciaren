# SPDX-License-Identifier: AGPL-3.0-only
"""Shared driver logic for the pandas / polars code generators.

Everything that must behave identically in both generated dialects lives here,
so a fix in one driver cannot silently miss the other: edge → variable
resolution (including multi-output ``sourceHandle`` routing), input-variable
collection, import ordering, SQL engine-variable allocation, and liveness.

The non-trivial bit is liveness analysis: every node's dataframe variable is
dead once its **last** consumer has run. Both generators use it two ways —
to reuse a dead variable as the consumer's output (``df_1 = df_1.head(5)``
instead of minting ``df_2``), and, under the optional ``del``
("free intermediates") mode, to release variables that could not be reused
(see :class:`DelScheduler`).
"""

import re
from typing import Any

from app.engine.sql_codegen import engine_url_expr

_SELF_ASSIGN = re.compile(r"^(\w+) = \1$")


def strip_self_assign(code: str) -> str:
    """Drop no-op ``x = x`` lines from an emitted snippet.

    Emitters that build their output incrementally seed it with ``dst = src``
    before appending per-item lines; under variable reuse dst and src are the
    same name and the seed degenerates to ``df_1 = df_1``. Filtering here keeps
    every emitter's seed-line idiom valid instead of making each one dst==src
    aware."""
    lines = [line for line in code.split("\n") if not _SELF_ASSIGN.match(line)]
    return "\n".join(lines) or code


def incoming_by_target(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Index a graph's edges by target node id (every node gets an entry)."""
    incoming: dict[str, list[dict[str, Any]]] = {n["id"]: [] for n in graph["nodes"]}
    for edge in graph.get("edges", []):
        incoming[edge["target"]].append(edge)
    return incoming


def edge_source_var(node_outputs: dict[str, dict[str, str]], edge: dict[str, Any]) -> str:
    """The variable an edge carries, honoring ``sourceHandle`` for multi-output nodes."""
    outs = node_outputs[edge["source"]]
    handle = edge.get("sourceHandle")
    if handle and handle in outs:
        return outs[handle]
    if "out" in outs:
        return outs["out"]
    return next(iter(outs.values()))


def collect_input_vars(
    edges_in: list[dict[str, Any]],
    node_outputs: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Map a node's input handles to source variables. A repeated handle (variadic
    concat) is disambiguated with the edge's position (``in``, ``in_1``, …)."""
    input_vars: dict[str, str] = {}
    for i, e in enumerate(edges_in):
        handle = e.get("targetHandle") or "in"
        if handle in input_vars:
            handle = f"{handle}_{i}"
        input_vars[handle] = edge_source_var(node_outputs, e)
    return input_vars


_PLACEHOLDER_EXT = {
    "csv": ".csv",
    "tsv": ".tsv",
    "excel": ".xlsx",
    "parquet": ".parquet",
    "json": ".json",
    "jsonl": ".jsonl",
    "text": ".txt",
}


def placeholder_input_path(source_type: str) -> str:
    """Fallback filename for an input node whose dataset id isn't in the caller's
    ``dataset_paths`` map, matching the node's format — pd.read_excel('input.xlsx'),
    not pd.read_excel('input.csv')."""
    return f"input{_PLACEHOLDER_EXT.get(source_type, '.csv')}"


def ordered_imports(imports: list[str]) -> list[str]:
    """``import x`` lines first, then ``from x import y`` lines, each sorted."""
    plain = sorted(i for i in imports if i.startswith("import "))
    froms = sorted(i for i in imports if not i.startswith("import "))
    return plain + froms


def sql_engine_var(
    connection_id: str,
    connections: dict[str, dict[str, Any]],
    engine_vars: dict[str, str],
    lines: list[str],
) -> str:
    """The sqlalchemy engine variable for a connection, emitting its
    ``create_engine`` line into ``lines`` on first use."""
    if connection_id not in engine_vars:
        var = f"_engine_{len(engine_vars) + 1}"
        info = connections.get(connection_id, {"provider": "sqlite", "database": ""})
        lines.append(f"{var} = create_engine({engine_url_expr(info)})")
        engine_vars[connection_id] = var
    return engine_vars[connection_id]


def last_consumer_index(order: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Map each source node id to the position (in ``order``) of its *last* consumer.

    A node that fans out to several downstream nodes — or whose result a later
    join needs — must stay alive until the highest-positioned consumer has run,
    so we take the maximum. Nodes with no consumers (e.g. output sinks) are
    absent from the result. ``order`` is the topological execution order, so a
    consumer's index is always greater than its producer's.
    """
    position = {node_id: i for i, node_id in enumerate(order)}
    last: dict[str, int] = {}
    for edge in edges:
        source, target = edge["source"], edge["target"]
        if source not in position or target not in position:
            continue
        idx = position[target]
        if idx > last.get(source, -1):
            last[source] = idx
    return last


def reusable_output_var(
    idx: int,
    incoming_edges: list[dict[str, Any]],
    node_outputs: dict[str, dict[str, str]],
    n_output_handles: int,
    last_use: dict[str, int],
) -> str | None:
    """The input variable the node at position ``idx`` may overwrite, or ``None``.

    Every node's generated code fully evaluates its input before (re)assigning
    its output variable, so a single-output node that is the *last* consumer of
    its single input can write its result back into the input's variable
    (``df_1 = df_1.head(5)``) instead of minting a fresh one — the exported
    script then reads like hand-written code. Reuse is safe iff:

    - the node has exactly one incoming edge and exactly one output handle;
    - the source node produced exactly one variable (liveness is tracked per
      node, not per handle, so reusing one handle's variable could clobber a
      sibling handle another consumer still needs);
    - this node is the source's last consumer in emission order, so no later
      node reads the variable.
    """
    if n_output_handles != 1 or len(incoming_edges) != 1:
        return None
    source = incoming_edges[0]["source"]
    outs = node_outputs.get(source)
    if outs is None or len(outs) != 1:
        return None
    if last_use.get(source) != idx:
        return None
    return next(iter(outs.values()))


class DelScheduler:
    """Emits ``del`` statements once a variable's last consumer has run.

    The risk with freeing intermediates is deleting a frame a later node still
    needs; scheduling strictly at ``last_use`` positions (and never at the final
    node, whose result is the script's point) makes that impossible. Disabled
    instances are inert, so drivers can call unconditionally.
    """

    def __init__(self, order: list[str], last_use: dict[str, int], enabled: bool) -> None:
        self._last_use = last_use
        self._final_idx = len(order) - 1
        self._enabled = enabled
        self._pending: dict[int, list[str]] = {}

    def schedule(self, node_id: str, outs: dict[str, str]) -> None:
        """Queue a just-emitted node's output for deletion after its last consumer.
        Multi-output liveness is per node, not per handle, so only single-output
        nodes are freed."""
        if not self._enabled or len(outs) != 1:
            return
        li = self._last_use.get(node_id)
        if li is not None and li < self._final_idx:
            self._pending.setdefault(li, []).append(next(iter(outs.values())))

    def cancel(self, idx: int, var: str) -> None:
        """A consumer at position ``idx`` took ``var`` over as its own output
        (variable reuse) — it must not be deleted there."""
        if var in self._pending.get(idx, []):
            self._pending[idx].remove(var)

    def flush(self, idx: int) -> list[str]:
        """The ``del`` lines to append after emitting the node at position ``idx``.
        Popped at *every* position — a variable's last consumer may be an output
        sink, which produces no variable of its own."""
        return [f"del {var}" for var in self._pending.pop(idx, [])]
